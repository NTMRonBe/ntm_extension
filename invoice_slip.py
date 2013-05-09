import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _

class regional_income(osv.osv):
    _name = 'regional.income'
    _description = 'Regional Income'
    _columns = {
        'name':fields.char('Income Name',size=64),
        'code':fields.char('Code',size=16,help = "Please use small caps"),
        }
regional_income()

class regional_configuration(osv.osv):
    _name = 'regional.configuration'
    _description = "Regional Branches"
    _columns = {
        'name':fields.char('Name',size=64),
        'code':fields.char('Code',size=16),
        'journal_id':fields.many2one('account.journal','Journal')
        }
regional_configuration()

class regional_configuration_income(osv.osv):
    _name = 'regional.configuration.income'
    _description = "Branch Income"
    _columns = {
        'income_id':fields.many2one('regional.income','Expense Name'),
        'analytic_account':fields.many2one('account.analytic.account','Analytic Account'),
        'regional_config_id':fields.many2one('regional.configuration','Regional Configuration',ondelete='cascade'),
        }
regional_configuration_income()

class rc(osv.osv):
    _inherit = 'regional.configuration'
    _columns = {
        'income_ids':fields.one2many('regional.configuration.income','regional_config_id','Expenses'),
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
    
    _order = 'trans_date desc'
    def create(self, cr, uid, vals, context=None):
        new_id = super(invoice_slip, self).create(cr, uid, vals,context)
        return new_id
    def create_moves(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        for inv in self.read(cr, uid, ids,context=None):
            region_read = self.pool.get('regional.configuration').read(cr, uid, inv['region_id'][0],['journal_id'])
            amount = 0.00
            move = {
                'ref':inv['transaction_id'],
                'journal_id':region_read['journal_id'][0],
                'date':inv['trans_date'],
                'period_id':inv['period_id'][0],
            }
            move_id = move_pool.create(cr, uid, move)
            for line in inv['line_ids']:
                line_read = self.pool.get('invoice.slip.line').read(cr, uid, line, ['income_id','amount','comment'])
                amount +=line_read['amount']
                income_search = self.pool.get('regional.configuration.income').search(cr, uid, [('income_id','=',line_read['income_id'][0]),('regional_config_id','=',inv['region_id'][0])])
                income_id=False
                for income_line in income_search:
                    income_read = self.pool.get('regional.configuration.income').read(cr, uid, income_line,['analytic_account'])
                    analytic_read = self.pool.get('account.analytic.account').read(cr, uid, income_read['analytic_account'][0],['normal_account'])
                    move_line = {
                        'ref':inv['transaction_id'],
                        'name':line_read['comment'],
                        'journal_id':region_read['journal_id'][0],
                        'period_id':inv['period_id'][0],
                        'date':inv['trans_date'],
                        'account_id':analytic_read['normal_account'][0],
                        'credit':line_read['amount'],
                        'analytic_account_id':income_read['analytic_account'][0],
                        'move_id':move_id,
                        }
                    move_line_pool.create(cr, uid, move_line)
            partner_analytic = self.pool.get('account.analytic.account').search(cr, uid, [('partner_id','=',inv['partner_id'][0])])
            partner_name = inv['partner_id'][1]
            if not partner_analytic:
                raise osv.except_osv(_('Error !'), _('%s doesn\'t have any analytic account!')%partner_name)
            if partner_analytic:
                for partner_acc in partner_analytic:
                    acc_read = self.pool.get('account.analytic.account').read(cr, uid, partner_acc,['id','normal_account'])
                    debit = {
                        'name':inv['transaction_id'],
                        'journal_id':region_read['journal_id'][0],
                        'period_id':inv['period_id'][0],
                        'date':inv['trans_date'],
                        'account_id':acc_read['normal_account'][0],
                        'debit':amount,
                        'analytic_account_id':acc_read['id'],
                        'move_id':move_id,
                        }
                    move_line_pool.create(cr, uid, debit)
        return True
invoice_slip()

class invoice_slip_line(osv.osv):
    _name = 'invoice.slip.line'
    _description = "Invoice Slip Lines"
    _columns = {
        'income_id':fields.many2one('regional.income','Income Code'),
        'amount':fields.float('Amount',size=64),
        'comment':fields.text('Memo'),
        'slip_id':fields.many2one('invoice.slip','Invoice Slip',ondelete='cascade')
        }
    def create(self, cr, uid, vals, context=None):
        new_id = super(invoice_slip_line, self).create(cr, uid, vals,context)
        return new_id
    
        
invoice_slip_line()