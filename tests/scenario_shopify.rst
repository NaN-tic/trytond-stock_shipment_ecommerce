======================================
Stock Shipment Ecommerce Shop Scenario
======================================

Imports::

    >>> from proteus import Model
    >>> from decimal import Decimal
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company

Install stock_shipment_ecommerce::

    >>> config = activate_modules('stock_shipment_ecommerce')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party()
    >>> party.name = 'ShopOwner'
    >>> party.save()

Create Country::

    >>> Country = Model.get('country.country')
    >>> country = Country()
    >>> country.code = 'ES'
    >>> country.name = 'España'
    >>> country.save()

Create Subdivision::

    >>> Subdivision = Model.get('country.subdivision')
    >>> subdivision = Subdivision()
    >>> subdivision.code = 'ES-B'
    >>> subdivision.country = country
    >>> subdivision.name = 'Barcelona'
    >>> subdivision.type = 'province'
    >>> subdivision.save()

Create Product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('30')
    >>> template.party = party
    >>> product, = template.products
    >>> product.party_code = '0987654321-M'
    >>> template.save()

    >>> template2 = ProductTemplate()
    >>> template2.name = 'product2'
    >>> template2.default_uom = unit
    >>> template2.type = 'goods'
    >>> template2.list_price = Decimal('30')
    >>> template2.party = party
    >>> product2, = template2.products
    >>> product2.party_code = '1234567890'
    >>> template2.save()

Create Shop::

    >>> Warehouse = Model.get('stock.location')
    >>> warehouse, = Warehouse.find([('type', '=', 'warehouse')], limit=1)
    >>> Shop = Model.get('stock.shipment.ecommerce.shop')
    >>> shop = Shop()
    >>> shop.name = 'TestShop'
    >>> shop.type = 'shopify'
    >>> shop.api_key = 'testkey'
    >>> shop.api_password = 'testpass'
    >>> shop.url = 'https://this-is-my-test-show.myshopify.com/admin/api/unstable'
    >>> shop.party = party
    >>> shop.warehouse = warehouse
    >>> shop.save()

Update Shop Shipments::

    >>> Shipment = Model.get('stock.shipment.out')
    >>> shipments = Shipment.find()
    >>> len(shipments)
    0
    >>> shop.click('update_shop_shipments')
    >>> shipments = Shipment.find()
    >>> len(shipments)
    1
    >>> shipment, = shipments
    >>> len(shipment.outgoing_moves)
    2
    >>> len(shipment.inventory_moves)
    2
    >>> moves = sorted(shipment.inventory_moves, key=lambda x: x.product.name)
    >>> move = moves[0]
    >>> (move.product.name, move.quantity)
    ('product', 1.0)
    >>> move = moves[1]
    >>> (move.product.name, move.quantity)
    ('product2', 1.0)
