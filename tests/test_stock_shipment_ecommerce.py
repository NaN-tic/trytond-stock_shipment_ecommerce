# This file is part stock_shipment_ecommerce module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import unittest
import doctest

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_teardown, doctest_checker
from trytond.pool import Pool


class StockShipmentEcommerceTestCase(ModuleTestCase):
    'Test Stock Shipment Ecommerce module'
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

def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockShipmentEcommerceTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_shopify.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
