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

import os
import tools

from StringIO import StringIO
import base64
from tools.translate import _
from osv import osv, fields
import dbf

class voucher_file_import(osv.osv_memory):
    """ Import Voucher File """

    _name = "voucher.file.import"
    _description = "Import Voucher File"

    _columns = {
          'voucher_file': fields.binary('File .DBF file', required=True),
          'file_name': fields.char('File Name', size=128),
          'state':fields.selection([('init','init'),('done','done')], 'state', readonly=True),
    }

    _defaults = {  
        'state': 'init',
    }

    def importzip(self, cr, uid, ids, context):
        user = uid
        user_read =self.pool.get('res.users').read(cr, uid, user, ['company_id'])
        company_read = self.pool.get('res.company').read(cr, uid, user_read['company_id'][0],['voucher_dbf'])
        voucher_read = self.pool.get('voucher.distribution').read(cr, uid, context['active_id'],['name'])
        voucher_name = voucher_read['name']
        voucher_name = voucher_name.replace(' ','_')
        voucher_name = voucher_name.replace('/','_')
        filename=company_read['voucher_dbf']
        dbf_file = filename+voucher_name
        file = dbf_file+'.dbf'
        (data,) = self.browse(cr, uid, ids , context=context)
        module_data = data.voucher_file
        val = base64.decodestring(module_data)
        fp = open(file,'wb')
        fp.write(val)
        fp.close
        self.write(cr, uid, ids, {'state':'done'}, context)
        return True
    
    def distribute(self, cr, uid, ids, context):
        user = uid
        user_read =self.pool.get('res.users').read(cr, uid, user, ['company_id'])
        company_read = self.pool.get('res.company').read(cr, uid, user_read['company_id'][0],['voucher_dbf'])
        voucher_read = self.pool.get('voucher.distribution').read(cr, uid, context['active_id'],['name'])
        voucher_name = voucher_read['name']
        voucher_name = voucher_name.replace(' ','_')
        voucher_name = voucher_name.replace('/','_')
        filename=company_read['voucher_dbf']
        dbf_file = filename+voucher_name
        table = dbf.Table(dbf_file)
        table.open()
        postage_recovery = 0.00
        envelope_recovery = 0.00
        for rec in table:
            rec_name=str(rec.comm1)
            rec_comments = str(rec.comm2)
            rec_co1 = str(rec.battypecd)
            rec_batchddate = str(rec.batdt)
            rec_co2 = str(rec.batltr)
            rec_docnum = str(rec.docno)
            rec_code = str(rec.trancd)
            rec_code = rec_code.replace(' ','')
            sprice = (rec.amount)
            rec_amount = str(sprice)
            rec_amount = float(rec_amount)
            rec_amount = "%.2f" % rec_amount
            rec_amount = float(rec_amount) 
            vals = {
                'name':rec_name,
                'voucher_id':context['active_id'],
                'comments':rec_comments,
                'co1':rec_co1,
                'batch_date':rec_batchddate,
                'co2':rec_co2,
                'doc_num':rec_docnum,
                'code':rec_code,
                'amount':rec_amount,
                }
            if rec_code in ['AD','CK','CL','DG','DO','LI','MD','MI','MM','MP','MS','MU','MX','NT','PI','SU','TI','TS']:
                vals.update({'type':'mission'})
            elif rec_code in ['DV','VD']:
                vals.update({'type':'voucher'})
            if rec_code not in ['BD', 'CH', 'DP', 'GP', 'LP', 'PD', 'PG', 'PY', 'RF', 'ST', 'TR', 'V', 'WD', 'ME']:
                self.pool.get('voucher.distribution.line').create(cr, uid, vals)
            if rec_code=='ME':
                if rec_name.find('N@W')==0:
                    naw_vals = {
                        'voucher_id':context['active_id'],
                        'name':rec_comments,
                        'amount':rec_amount,
                        }
                    self.pool.get('voucher.distribution.natw.charge').create(cr, uid, naw_vals)
                if rec_name.find('N@W')==-1:
                    checker = rec_name.replace(' ','')
                    checker = checker.replace('&','')
                    checker = checker.lower()
                    if checker=='rcptformenvrecovery':
                        envelope_recovery = rec_amount
                    elif checker=='rcptpostagerecovery':
                        postage_recovery = rec_amount
            if rec_code in ['BD', 'CH', 'DP', 'GP', 'LP', 'PD', 'PG', 'PY', 'RF', 'ST', 'TR', 'V', 'WD']:
                name = rec_name
                if 'EMAIL CHARGE' in rec_name:
                    name = rec_comments
                vals = {
                    'voucher_id':context['active_id'],
                    'name':name,
                    'amount':rec_amount,
                    }
                self.pool.get('voucher.distribution.personal.section').create(cr, uid, vals)
        self.pool.get('voucher.distribution').write(cr, uid, context['active_id'],{'generated':True,'postage_recovery':postage_recovery,'envelope_recovery':envelope_recovery})
        return {'type': 'ir.actions.act_window_close'}

voucher_file_import()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: