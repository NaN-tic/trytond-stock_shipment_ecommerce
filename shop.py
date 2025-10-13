from datetime import datetime
from trytond.model import ModelSQL, ModelView, fields, Unique, DeactivableMixin
from trytond.pool import Pool, PoolMeta
from trytond.i18n import gettext
from trytond.exceptions import UserError
from trytond.pyson import Eval, Bool
import shopify
import json
import os.path


class Shop(DeactivableMixin, ModelSQL, ModelView):
    "Shop"
    __name__ = 'stock.shipment.ecommerce.shop'
    name = fields.Char('Name', required=True)
    type = fields.Selection([
        ('manual', 'Manual'),
        ('shopify', 'Shopify'),
        ], 'Type', required=True)
    api_key = fields.Char('API Key')
    api_password = fields.Char('API Password', strip=False)
    url = fields.Char('Shop URL')
    party = fields.Many2One('party.party', 'Party', required=True)
    warehouse = fields.Many2One('stock.location', 'Warehouse',
        domain=[
            ('type', '=', 'warehouse'),
        ], required=True)
    create_products = fields.Boolean('Create Products')
    last_shopify_shipment_id = fields.Integer('Last Shopify Shipment ID',
        readonly=True)
    last_shopify_shipment_id._sql_type = 'BIGINT'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        # required / invisible fields
        cls._required_fields = ['shopify']
        for field in ('api_key', 'api_password', 'url'):
            getattr(cls, field).states.update({
                    'required': Eval('type').in_(cls._required_fields),
                    'invisible': ~Eval('type').in_(cls._required_fields),
                    })
            getattr(cls, field).depends.add('type')
        cls.create_products.states.update({
                'invisible': ~Eval('type').in_(cls._required_fields),
                })
        cls.create_products.depends.add('type')
        # buttons
        cls._buttons.update({
            'update_shop_shipments': {
                'invisible': ~Eval('type').in_(cls._required_fields),
                'depends': ['type'],
                },
            })

    @staticmethod
    def default_type():
        return 'manual'

    @classmethod
    def update_shop_shipments_cron(cls):
        records = cls.search([])
        cls.update_shop_shipments(records)

    @classmethod
    @ModelView.button
    def update_shop_shipments(cls, records):
        for record in records:
            if hasattr(record, 'update_%s' % record.type):
                meth = getattr(record, 'update_%s' % record.type)
                meth()

    def get_shopify_orders(self):
        orders_list = []
        last_id = self.last_shopify_shipment_id or 0
        while True:
            try:
                current_list = shopify.Order.find(since_id=last_id, limit=250)
            except Exception:
                raise UserError(
                    gettext('stock_shipment_ecommerce.shop_connection_failed'))
            if not current_list:
                break
            orders_list.extend(current_list)
            last_id = orders_list[-1].id

        self.last_shopify_shipment_id = last_id
        self.save()
        return orders_list

    def update_shopify(self):
        pool = Pool()
        Shipment = pool.get('stock.shipment.out')
        Address = pool.get('party.address')
        Party = pool.get('party.party')
        PartyIdentifier = pool.get('party.identifier')
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        Country = pool.get('country.country')
        Subdivision = pool.get('country.subdivision')
        ProductUOM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        url = 'https://{}:{}@{}'.format(self.api_key, self.api_password,
            self.url)

        shopify.ShopifyResource.set_site(url)

        if self.name != 'TestShop':
            # real update
            orders_list = self.get_shopify_orders()
        else:
            # test update
            # loads order_1.json into orders list
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                'tests/order_1.json')
            with open(path) as json_file:
                order_json = json.load(json_file)['order']
            order = shopify.Order(order_json)
            orders_list = [order]

        unit_uom = ProductUOM(ModelData.get_id('product', 'uom_unit'))

        default_values = Shipment.default_get(Shipment._fields.keys(),
                with_rec_name=False)

        shipments_to_save = []
        for order in orders_list:
            existent_shipment = Shipment.search([
                ('shop_order_id', '=', str(order.id)),
                ('shop', '=', self)
                ])
            if existent_shipment:
                continue

            # In some cases (ie, the customer will pick the product from the
            # warehouse) the shipping_address may not exist
            shipping_address = getattr(order, 'shipping_address', None)

            if hasattr(order, 'customer') and order.customer:
                customer = order.customer
            else:
                raise UserError(
                    gettext('stock_shipment_ecommerce.missing_customer',
                        order=order.order_number, shop=self.name))

            parties = Party.search([
                    ('identifiers.code', '=', str(customer.id)),
                    ('identifiers.type', '=', 'shop')
                    ], limit=1)
            if not parties and shipping_address:
                party = Party()
                party.name = shipping_address.name
                party.shop = self
                party.save()
                identifier = PartyIdentifier()
                identifier.party = party
                identifier.type = 'shop'
                identifier.code = customer.id
                identifier.save()
            elif not shipping_address:
                party = self.party
            else:
                party, = parties
                if party.name != shipping_address.name:
                    party.name = shipping_address.name
                    party.save()
            if shipping_address:
                address_exist = Address.search([
                        ('party', '=', party),
                        ('street', '=', shipping_address.address1),
                        ('postal_code', '=', shipping_address.zip)
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
                        if '-' not in shipping_address.province_code:
                            sub_code = (address.country.code + '-'
                                + shipping_address.province_code)
                        else:
                            sub_code = shipping_address.province_code
                        subdivisions = Subdivision.search(
                            [('code', '=', sub_code)], limit=1)
                        if not subdivisions:
                            subdivisions = Subdivision.search(
                                    [('code', 'ilike', sub_code + '%')], limit=1)
                        else:
                            address.subdivision, = subdivisions
                    address.party = party
                    address.postal_code = shipping_address.zip
                    address.delivery = True
                    address.save()
            else:
                addresses = Address.search([('party', '=', party)])
                if addresses:
                    address = addresses[0]
                else:
                    raise UserError(gettext(
                                'stock_shipment_ecommerce.no_pickup_address',
                                party=party.rec_name, order=order.order_number,
                                shop=self.name))

            shipment = Shipment(**default_values)
            shipment.sale_date = datetime.strptime(order.created_at[0:10],
                "%Y-%m-%d").date()
            shipment.customer = party
            shipment.delivery_address = address
            shipment.origin_party = self.party
            shipment.reference = order.order_number
            shipment.shop_order_id = order.id
            shipment.shop = self.id
            shipment.warehouse = self.warehouse
            shipment.on_change_warehouse()
            shipment.state = 'draft'
            shipment.json_order = order.to_json()
            shipment.customer_phone_numbers = get_customer_phone_numbers(order)
            shipment.comment = order.note or ''
            attributes = []
            for attribute in order.note_attributes:
                attributes += list(attribute.to_dict().values())
                shipment.comment += '\n'.join(attribute.to_dict().values())
            shipments_to_save.append(shipment)

            moves = []
            for line in order.line_items:
                products = Product.search([
                        ('template.party', '=', self.party),
                        ('party_code', '=', line.sku),
                        ], limit=1)
                if not products:
                    if not self.create_products:
                        raise UserError(
                            gettext('stock_shipment_ecommerce.missing_product',
                                product=line.sku,
                                order=order.order_number, shop=self.name))
                    template = Template()
                    template.name = line.title
                    template.type = 'goods'
                    template.default_uom = unit_uom
                    template.party = self.party
                    template.list_price = 0
                    template.save()
                    product = Product()
                    product.code = line.sku
                    product.cost_price = 0
                    product.template = template
                    if not line.sku:
                        raise UserError(
                            gettext(
                                'stock_shipment_ecommerce.no_product_sku',
                                product=template.name,
                                order=order.order_number,
                                shop=self.name))
                    product.party_code = line.sku
                    product.save()
                    products = [product]
                product, = products

                move = Move()
                move.shipment = shipment
                move.from_location = self.warehouse.output_location
                move.to_location = self.party.customer_location
                move.quantity = line.quantity
                move.product = product
                move.unit = product.default_uom
                move.unit_price = product.list_price_used
                move.currency = shipment.company.currency
                moves.append(move)
            shipment.outgoing_moves = tuple(moves)
        Shipment.save(shipments_to_save)
        Shipment.wait(shipments_to_save)

def get_customer_phone_numbers(order):
    if getattr(order, 'shipping_address', None):
        phones = [
            order.phone,
            order.shipping_address.phone,
            order.customer.phone
            ]
    else:
        phones = [
            order.phone,
            order.customer.phone
            ]
    phones = set([n.strip() for n in phones if n and n.strip()])
    return ', '.join(phones)


class ShipmentMixin:
    __slots__ = ()
    origin_party = fields.Many2One('party.party', 'Origin Party',
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])


class ShipmentOutReturn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'
    sale_date = fields.Date('Sale Date')


class ShipmentIn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'


class ShipmentInReturn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'


class ShipmentOut(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'
    shop = fields.Many2One('stock.shipment.ecommerce.shop', 'Shop')
    shop_order_id = fields.Char('Shop Order ID', readonly=True)
    json_order = fields.Text("Order's JSON", readonly=True)
    customer_phone_numbers = fields.Char('Customer Phone Numbers')
    sale_date = fields.Date('Sale Date')

    @classmethod
    def __setup__(cls):
        super(ShipmentOut, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('shipment_ecommerce_uniq', Unique(t, t.shop, t.shop_order_id),
                'stock_shipment_ecommerce.msg_shipment_ecommerce_unique'),
            ]

    @fields.depends('customer', 'customer_phone_numbers')
    def on_change_customer(self):
        super(ShipmentOut, self).on_change_customer()
        if self.customer and not self.customer_phone_numbers:
            self.customer_phone_numbers = ', '.join(
                set([self.customer.phone, self.customer.mobile]))

    @classmethod
    def copy(cls, shipments, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('shop_order_id', None)
        return super(ShipmentOut, cls).copy(shipments, default=default)


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'
    party = fields.Many2One('party.party', 'Party')


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
    party_code = fields.Char('Party Code',
        states={'required': Bool(Eval('party'))})


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super(Cron, cls).__setup__()
        cls.method.selection.append(
            ('stock.shipment.ecommerce.shop|update_shop_shipments_cron',
            "Update Shipments"),
            )
