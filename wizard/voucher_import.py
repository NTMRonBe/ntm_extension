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
        missionary_subtotal = 0.00
        recovery_charges = 0.00
        natw_total_charges = 0.00
        phna_pool = []
        phna_accs = self.pool.get('voucher.distribution.missionaries').search(cr, uid, [])
        for phna in phna_accs:
            phna_read = self.pool.get('voucher.distribution.missionaries').read(cr, uid, phna,context=None)
            phna_name = phna_read['name']
            phna_name = phna_name.replace(' ','')
            phna_name = phna_name.replace('&','')
            phna_name = phna_name.lower()
            phna_pool.append(phna_name)
        print phna_pool
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
            if rec_code in ['AD','CK','CL','DG','DO','LI','MI','MM','MP','MS','MU','MX','NT','PI','SU','TI','TS']:
                vals.update({'type':'mission'})
            elif rec_code in ['DV','VD']:
                phnational = rec_name.lower()
                phnational = phnational.replace(' ','')
                phnational = phnational.replace('&','')
                if phnational in phna_pool:
                    for phna in phna_accs:
                        phna_read = self.pool.get('voucher.distribution.missionaries').read(cr, uid, phna,context=None)
                        acc_read = self.pool.get('account.analytic.account').read(cr, uid, phna_read['account_id'][0],['name'])
                        phna_name = phna_read['name']
                        phna_name = phna_name.replace(' ','')
                        phna_name = phna_name.replace('&','')
                        phna_name = phna_name.lower()
                        if phnational == phna_name:
                            amount = rec_amount * -1
                            val_name = False
                            if phna_read['national']==True:
                                val_name = 'Philippine National'
                            elif phna_read['national']==False:
                                vouch_read = self.pool.get('voucher.distribution').read(cr, uid, context['active_id'],['name'])
                                val_name = vouch_read['name']
                            phna_vals = {
                                    'name':val_name,
                                    'comment':rec_name,
                                    'amount':amount,
                                    'voucher_id':context['active_id'],
                                    'analytic_account_id':phna_read['account_id'][0],
                                    'account_name':acc_read['name'],
                                    }
                            self.pool.get('voucher.distribution.voucher.transfer').create(cr, uid, phna_vals)
                elif phnational not in phna_pool:
                    amount = rec_amount * -1
                    val_name = 'For Account Assignment'
                    phna_vals = {
                            'name':val_name,
                            'comment':rec_name,
                            'amount':amount,
                            'voucher_id':context['active_id'],
                            }
                    self.pool.get('voucher.distribution.voucher.transfer').create(cr, uid, phna_vals)
            if rec_code not in ['BD', 'CH', 'DP', 'GP', 'LP', 'PD', 'PG', 'PY', 'RF', 'ST', 'TR', 'V', 'WD', 'ME','DV','VD']:
                self.pool.get('voucher.distribution.line').create(cr, uid, vals)
            if rec_code=='ME':
                if rec_name.find('N@W')==0:
                    rec_amount = rec_amount * -1
                    naw_vals = {
                        'voucher_id':context['active_id'],
                        'name':rec_comments,
                        'amount':rec_amount,
                        }
                    self.pool.get('voucher.distribution.natw.charge').create(cr, uid, naw_vals)
                    natw_total_charges += rec_amount
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
                rec_amount = rec_amount * -1
                if 'NTMA' in rec_name:
                    name = rec_name + rec_comments
                if 'BOOKSTORE' in rec_name:
                    name = rec_name.replace('BOOKSTORE','')
                    name = name.replace('INVOICE','')
                    name = name.replace(' ','')
                    comments = rec_comments.replace(' ','')
                    name = name + ' ' + comments
                vals = {
                    'voucher_id':context['active_id'],
                    'name':name,
                    'amount':rec_amount,
                    }
                self.pool.get('voucher.distribution.personal.section').create(cr, uid, vals)
            if rec_code in ['DG','MI','DP'] and rec_amount>0.00:
                missionary_subtotal -=rec_amount
        recovery_charges = postage_recovery + envelope_recovery
        self.pool.get('voucher.distribution').write(cr, uid, context['active_id'],{'generated':True,
                                                                                   'postage_recovery':postage_recovery,
                                                                                   'missionary_subtotal':missionary_subtotal,
                                                                                   'natw_total_charges':natw_total_charges,
                                                                                   'recovery_charges':recovery_charges,
                                                                                   'envelope_recovery':envelope_recovery})
        return {'type': 'ir.actions.act_window_close'}

voucher_file_import()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: