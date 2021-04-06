# This file is part stock_shipment_ecommerce module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import unittest
import doctest

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import doctest_teardown, doctest_checker


class StockShipmentEcommerceTestCase(ModuleTestCase):
    'Test Stock Shipment Ecommerce module'
    module = 'stock_shipment_ecommerce'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockShipmentEcommerceTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_shopify.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
