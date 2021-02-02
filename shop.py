from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.i18n import gettext
from trytond.exceptions import UserError
import shopify
import json
import os.path
from trytond.pyson import Eval, Bool


class Shop(ModelSQL, ModelView):
    "Shop"
    __name__ = 'stock.shipment.ecommerce.shop'
    name = fields.Char('Name', required=True)
    type = fields.Selection([('shopify', 'Shopify'), ], 'Type', required=True)
    api_key = fields.Char('API Key',
        states={'required': Eval('type') == 'shopify'}, depends=['type'])
    api_password = fields.Char('API Password',
        states={'required': Eval('type') == 'shopify'}, depends=['type'])
    url = fields.Char('Shop URL')
    party = fields.Many2One('party.party', 'Party', required=True)
    warehouse = fields.Many2One('stock.location', 'Warehouse',
        domain=[('type', '=', 'warehouse')], required=True)

    @classmethod
    def update_shop_shipments_cron(cls):
        records = cls.search([])
        cls.update_shop_shipments(records)

    @classmethod
    @ModelView.button
    def update_shop_shipments(cls, records):
        for record in records:
            meth = getattr(record, 'update_%s' % record.type)
            meth()

    def update_shopify(self):
        pool = Pool()
        Shipment = pool.get('stock.shipment.out')
        Address = pool.get('party.address')
        Party = pool.get('party.party')
        PartyIdentifier = pool.get('party.identifier')
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        Country = pool.get('country.country')
        Subdivision = pool.get('country.subdivision')
        url = 'https://{}:{}@{}'.format(self.api_key, self.api_password, self.url)

        shopify.ShopifyResource.set_site(url)

        if self.name != 'TestShop':
            # real update
            try:
                orders_list = shopify.Order.find()
            except:
                raise UserError(
                    gettext('stock_shipment_ecommerce.shop_connection_failed'))
        else:
            # test update
            # loads order_1.json into orders list
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                'tests/order_1.json')
            with open(path) as json_file:
                order_json = json.load(json_file)['order']
            order = shopify.Order(order_json)
            orders_list = [order]

        shipments_to_save = []
        for order in orders_list:
            existent_shipment = Shipment.search([
                ('shop_order_id', '=', order.id),
                ('shop', '=', self.id)
                ])
            if existent_shipment:
                continue

            shipping_address = order.shipping_address
            if hasattr(order, 'customer') and order.customer:
                customer = order.customer
            else:
                raise UserError(
                    gettext('stock_shipment_ecommerce.missing_customer',
                        order=order.order_number, shop=self.name))

            parties = Party.search([
                    ('identifiers.code', '=', customer.id),
                    ('identifiers.type', '=', 'shop')
                    ], limit=1)
            if not parties:
                party = Party()
                party.name = shipping_address.name
                party.shop = self
                party.save()
                identifier = PartyIdentifier()
                identifier.party = party
                identifier.type = 'shop'
                identifier.code = customer.id
                identifier.save()
            else:
                party, = parties
                if party.name != shipping_address.name:
                    party.name = shipping_address.name
                    party.save()

            address_exist = Address.search([
                    ('party', '=', party),
                    ('street', '=', shipping_address.address1),
                    ('zip', '=', shipping_address.zip)
                    ])
            if address_exist:
                address = address_exist[0]
            else:
                address = Address()
                address.street = shipping_address.address1
                address.city = shipping_address.city
                countries = Country.search([
                        ('code', '=', shipping_address.country_code)], limit=1)
                if not countries:
                    raise UserError(
                        gettext('stock_shipment_ecommerce.country_not_found',
                            order=order.order_number, shop=self.name))
                address.country, = countries
                if shipping_address.province_code:
                    sub_code = (address.country.code + '-'
                        +shipping_address.province_code)
                    subdivisions = Subdivision.search([('code', '=', sub_code)])
                    if not subdivisions:
                        raise UserError(
                            gettext('stock_shipment_ecommerce.'
                                'subdivision_not_found',
                                 order=order.order_number, shop=self.name))
                    else:
                        address.subdivision, = subdivisions
                address.party = party
                address.zip = shipping_address.zip
                address.delivery = True
                address.save()

            shipment = Shipment()
            shipment.customer = party
            shipment.delivery_address = address
            shipment.origin_party = self.party
            shipment.reference = order.order_number
            shipment.shop_order_id = order.id
            shipment.shop = self.id
            shipment.warehouse = self.warehouse
            shipment.state = 'draft'
            shipment.json_order = order.to_json()
            shipment.customer_phone_numbers = get_customer_phone_numbers(order)
            shipments_to_save.append(shipment)

            moves = []
            for line in order.line_items:
                move = Move()
                move.shipment = shipment
                move.from_location = self.warehouse.output_location
                move.to_location = self.party.customer_location
                move.quantity = line.quantity
                products = Product.search([
                        ('template.party', '=', self.party),
                        ('party_code', '=', line.sku),
                        ], limit=1)
                if not products:
                    raise UserError(
                        gettext('stock_shipment_ecommerce.missing_product',
                            product=line.sku,
                            order=order.order_number, shop=self.name))

                product, = products
                move.product = product
                move.uom = product.default_uom
                move.unit_price = product.list_price
                moves.append(move)
            shipment.outgoing_moves = tuple(moves)
        Shipment.save(shipments_to_save)
        Shipment.wait(shipments_to_save)

    @classmethod
    def __setup__(cls):
        super(Shop, cls).__setup__()
        cls._buttons.update({
            'update_shop_shipments': {},
            })


def get_customer_phone_numbers(order):
    phones = [
        order.phone,
        order.shipping_address.phone,
        order.customer.phone
        ]
    phones = set([n.strip() for n in phones if n and n.strip()])
    return ', '.join(phones)


class ShipmentMixin:
    origin_party = fields.Many2One('party.party', 'Origin Party')


class ShipmentOutReturn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'
    sale_date = fields.Date('Sale Date')

class ShipmentIn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'


class ShipmentInReturn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'


class ShipmentOut(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'
    shop = fields.Many2One('stock.shipment.ecommerce.shop', 'Shop',
        readonly=True)
    shop_order_id = fields.Char('Shop Order ID', readonly=True)
    json_order = fields.Text("Order's JSON", readonly=True)
    customer_phone_numbers = fields.Char('Customer Phone Numbers')
    sale_date = fields.Date('Sale Date')

    @fields.depends('customer', 'customer_phone_numbers')
    def on_change_customer(self):
        super(ShipmentOut, self).on_change_customer()
        if self.customer and not self.customer_phone_numbers:
            self.customer_phone_numbers = ', '.join(
                set([self.customer.phone, self.customer.mobile]))


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'
    shop = fields.Many2One('stock.shipment.ecommerce.shop', 'Shop',
        readonly=True)


class PartyIdentifier(metaclass=PoolMeta):
    __name__ = 'party.identifier'

    @classmethod
    def __setup__(cls):
        super(PartyIdentifier, cls).__setup__()
        selection = ('shop', 'Shop')
        if selection not in cls.type.selection:
            cls.type.selection.append(selection)


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'
    party = fields.Many2One('party.party', 'Party')


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
    party_code = fields.Char('Party Code',
        states={'required': Bool(Eval('party'))}, depends=['party'])


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super(Cron, cls).__setup__()
        cls.method.selection.append(
            ('stock.shipment.ecommerce.shop|update_shop_shipments_cron',
            "Update Shipments"),
            )
