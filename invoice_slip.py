import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _

class invoice_slip_upload(osv.osv):
    _name = 'invoice.slip.upload'
    _description='Invoice Slips / Regional Files Uploader'
    _columns = {
            'transaction_id':fields.char('Transaction ID',size=64),
            'transaction_type':fields.char('Transaction Type',size=64),
            'debit_account':fields.char('Debit Account',size=16),
            'debit_fullname':fields.char('Account Name',size=100),
            'comment':fields.text('Memo'),
            'invoice_date':fields.date('Invoice Date'),
            'user_id':fields.char('Encoder',size=100),
            'credit_account':fields.char('Credit Account',size=16),
            'credit_fullname':fields.char('Account Name',size=100),
            'currency':fields.many2one('res.currency','Currency ID'),
            'imported':fields.boolean('Imported'),
            'amount':fields.float('Amount'),
            }
invoice_slip_upload()

class invoice_slip(osv.osv):
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    _name = 'invoice.slip'
    _description = "Invoice Slips / Regional Files"
    _columns = {
            'transaction_id':fields.char('Transaction ID',size=64),
            'transaction_type':fields.char('Transaction Type',size=64),
            'debit_account':fields.many2one('account.analytic.account','Debit Account'),
            'comment':fields.text('Memo'),
            'journal_id':fields.many2one('account.journal','Journal'),
            'invoice_date':fields.date('Invoice Date'),
            'period_id':fields.many2one('account.period','Period'),
            'user_id':fields.char('Encoder',size=100),
            'credit_account':fields.many2one('account.account','Credit Account'),
            'currency':fields.many2one('res.currency','Currency ID'),
            'line_ids': fields.one2many('invoice.slip.line', 'slip_id', 'Invoice Slip Lines '),
            'state':fields.selection([('draft','Draft'),('posted','Posted')],'State'),
            }
    
    _order = 'invoice_date desc'
    def create(self, cr, uid, vals, context=None):
        new_id = super(invoice_slip, self).create(cr, uid, vals,context)
        return new_id
    def create_moves(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        
        for inv in self.browse(cr, uid, ids):
            move = {
                'name':inv.transaction_id,
                'journal_id':inv.journal_id.id,
                'date':inv.invoice_date,
                'period_id':inv.period_id and inv.period_id.id or False,
            }
        return True
invoice_slip()

class invoice_slip_line(osv.osv):
    _name = 'invoice.slip.line'
    _description = "Invoice Slip Lines"
    _columns = {
        'name':fields.char('Item', size=64),
        'amount':fields.float('Amount',size=64),
        'slip_id':fields.many2one('invoice.slip','Invoice Slip')
        }
    def create(self, cr, uid, vals, context=None):
        new_id = super(invoice_slip_line, self).create(cr, uid, vals,context)
        return new_id
    
        
invoice_slip_line()