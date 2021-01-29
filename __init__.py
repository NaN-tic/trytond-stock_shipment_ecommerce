# This file is part stock_shipment_ecommerce module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import shop


def register():
    Pool.register(
        shop.Cron,
        shop.Shop,
        shop.ShipmentOut,
        shop.ShipmentOutReturn,
        shop.ShipmentIn,
        shop.ShipmentInReturn,
        shop.Party,
        shop.PartyIdentifier,
        shop.Template,
        shop.Product,
        module='stock_shipment_ecommerce', type_='model')
    Pool.register(
        module='stock_shipment_ecommerce', type_='wizard')
    Pool.register(
        module='stock_shipment_ecommerce', type_='report')
