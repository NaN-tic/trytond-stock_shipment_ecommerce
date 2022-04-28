
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool
from trytond.modules.company.tests import CompanyTestMixin


class StockShipmentEcommerceTestCase(CompanyTestMixin, ModuleTestCase):
    'Test StockShipmentEcommerce module'
    module = 'stock_shipment_ecommerce'

    @with_transaction()
    def test_party_identifiers(self):
        'Party Identifiers'
        pool = Pool()
        Configuration = pool.get('party.configuration')
        PartyIdentifier = pool.get('party.identifier')

        _TYPE = ('shop', 'Shop')
        self.assertTrue(_TYPE in Configuration.identifier_types.selection)
        self.assertTrue(_TYPE in PartyIdentifier.get_types())


del ModuleTestCase
