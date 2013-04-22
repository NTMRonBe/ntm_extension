import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _

class regional_expenses(osv.osv):
    _name = 'regional.expenses'
    _description = 'Regional Expenses'
    _columns = {
        'name':fields.char('Expense Name',size=64),
        'code':fields.char('Code',size=16,help = "Please use small caps"),
        }
regional_expenses()

class regional_configuration(osv.osv):
    _name = 'regional.configuration'
    _description = "Regional Branches"
    _columns = {
        'name':fields.char('Name',size=64),
        'code':fields.char('Code',size=16),
        }
regional_configuration()

class regional_configuration_expenses(osv.osv):
    _name = 'regional.configuration.expenses'
    _description = "Branch Expenses"
    _columns = {
        'expense_id':fields.many2one('regional.expenses','Expense Name'),
        'journal_id':fields.many2one('account.journal','Normal Journal'),
        'analytic_account':fields.many2one('account.analytic.account','Analytic Account'),
        'regional_config_id':fields.many2one('regional.configuration','Regional Configuration',ondelete='cascade'),
        }
regional_configuration_expenses()

class rc(osv.osv):
    _inherit = 'regional.configuration'
    _columns = {
        'expense_ids':fields.one2many('regional.configuration.expenses','regional_config_id','Expenses'),
        }
rc()

class invoice_slip_upload(osv.osv):
    _name = 'invoice.slip.upload'
    _description='Invoice Slips / Regional Files Uploader'
    _columns = {
            'transaction_id':fields.char('Transaction ID',size=64),
            'transaction_type':fields.char('Transaction Type',size=64),
            'partner_id':fields.char('Missionary',size=64),
            'comment':fields.text('Memo'),
            'trans_date':fields.date('Invoice Date'),
            'user_id':fields.char('Encoder',size=100),
            'imported':fields.boolean('Imported'),
            'amount':fields.float('Amount'),
            'region_id':fields.char('Region Code',size=6),
            'expense_code':fields.char('Expense Code',size=16),
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
            'region_id':fields.many2one('regional.configuration','Region'),
            'trans_date':fields.date('Invoice Date'),
            'period_id':fields.many2one('account.period','Period'),
            'user_id':fields.char('Encoder',size=100),
            'line_ids': fields.one2many('invoice.slip.line', 'slip_id', 'Invoice Slip Lines '),
            'state':fields.selection([('draft','Draft'),('posted','Posted')],'State'),
            'partner_id':fields.many2one('res.partner','Missionary'),
            }
    
    _defaults = {'state':'draft'}
    
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
        'expense_id':fields.many2one('regional.expenses','Expense Code'),
        'amount':fields.float('Amount',size=64),
        'comment':fields.text('Memo'),
        'slip_id':fields.many2one('invoice.slip','Invoice Slip',ondelete='cascade')
        }
    def create(self, cr, uid, vals, context=None):
        new_id = super(invoice_slip_line, self).create(cr, uid, vals,context)
        return new_id
    
        
invoice_slip_line()