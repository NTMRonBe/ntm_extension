# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    "name" : "NTM Extensions",
    "version" : "1.0",
    "author" : "Auberon Solutions, Inc.",
    "category": 'Generic Modules/Accounting',
    "description": """
    NTM Extensions
    """,
    'website': '',
    'init_xml': [],
    "depends" : ["account","account_accountant","account_cancel","account_chart","account_voucher","base","analytic","fetchmail","account_budget","email_template"],
    
    
    'update_xml': ["data.xml","ntm_extensions_view.xml"
                   ,"users_view.xml",
                   "security/ntm_security.xml",
                   "account_revaluation_view.xml",
                   "wizard/user_set_location_view.xml",
                   #"wizard/rec_exporter.xml",
                   "soa_view.xml",
                   "wizard/upload_view.xml",
                   "bank_transfer_view.xml",
                   "wizard/account_analytic_statement_view.xml",
                   "phone_bill_view.xml",
                   "wizard/voucher_import_view.xml",
                   "income_distribution_view.xml",
                   "expense_distribution_view.xml",
                   "forex_view.xml",
                   "forex_data.xml",
                   "ft_data.xml",
                   "account_pettycash/account_pettycash_view.xml",
                   "account_pettycash/pc_sequence.xml",
                   "account_pettycash/pcr_view.xml",
                   "account_pettycash/pcl_view.xml",
                   "fund_transfer_view.xml",
                   "iat_view.xml",
                   "account_pettycash/crs_view.xml",
                   "opening_balance.xml",
                   "region_report_view.xml",
                   "vehicle_charging_view.xml",
                   "regional_uploader_view.xml",
                   "bank_recon_view.xml",
                   "dbe_view.xml",
                   "allocate_view.xml",
                   "recurring_view.xml",
                   "region_view.xml",
                   "revaluation_view.xml",
                   "database_view.xml",
                   "ntm_menu2.xml",
                   "ntm_menus.xml",
                   'security/ir.model.access.csv',
                   ],
    'demo_xml': [
    ],
    'test': [
            ],
    'installable': True,
    'active': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
