import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
from compiler.ast import Add

class bank_recon(osv.osv):
    _name = 'bank.recon'
    _description = "Bank Reconciliation"
    _columns = {
        'name':fields.char('Reconciliation #',size=64),
        'bank_id':fields.many2one('res.partner.bank','Bank'),
        'date':fields.date('Reconciliation Date'),
        'type':fields.selection([
                        ('check_clearing','Check Clearing'),
                        ('wire_transfer_clearing','Wire Transfer Clearing'),
                        ('fund_transfer_clearing','Fund Transfer Clearing'),
                        ]),
        'state':fields.selection([
                        ('draft','Draft'),
                        ('confirmed','Confirmed'),
                        ('reconciled','Reconciled'),
                        ],'State'),
        }
    _defaults = {
            'state':'draft',
            'date': lambda *a: time.strftime('%Y-%m-%d'),
            'name':'NEW',
            }
bank_recon()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,