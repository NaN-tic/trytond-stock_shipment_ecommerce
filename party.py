from trytond.model import fields
from trytond.pool import PoolMeta


class Configuration(metaclass=PoolMeta):
    __name__ = 'party.configuration'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.identifier_types.selection += [('shop', 'Shop')]

    def get_identifier_types(self):
        return super().get_identifier_types() + [('shop', 'Shop')]


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'
    shop = fields.Many2One('stock.shipment.ecommerce.shop', 'Shop')
