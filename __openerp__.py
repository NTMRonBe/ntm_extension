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
    "author" : "Roxly Rivero",
    "category": 'Generic Modules/Accounting',
    "description": """
    NTM Extensions
    """,
    'website': '',
    'init_xml': [],
    "depends" : ["account","base","analytic"],
    'update_xml': ["ntm_extensions_view.xml"
                   ,"data.xml"
                   ,"users_view.xml","account_revaluation_view.xml",
                   "wizard/user_set_location_view.xml",
                   "wizard/soa_sender.xml",
                   "wizard/dbf_reader.xml"
                   ,"forex_view.xml","account_pettycash/account_pettycash_view.xml","account_pettycash/pc_sequence.xml","account_pettycash/pcr_view.xml","account_pettycash/crs_view.xml"],
    'demo_xml': [
    ],
    'test': [
            ],
    'installable': True,
    'active': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
