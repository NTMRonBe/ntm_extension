import time
import datetime
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class direct_bank_expense(osv.osv):
    _name = 'direct.bank.expense'
    _description = "Direct Bank Expense"
    _columns = {
        'bank_id':fields.many2one('res.partner.bank','Bank Account'),
        'amount':fields.float('Amount to Distribute'),
        'name':fields.char('DBE #',size=16),
        'remarks':fields.text('Remarks'),
        'rdate':fields.date('Received Date'),
        'move_id':fields.many2one('account.move','Move Name'),
	'user_id':fields.many2one('res.users','Book Keeper'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'ref':fields.char('Reference',size=64),
        'state':fields.selection([
                        ('draft','Draft'),
                        ('distributed','Distributed'),
                        ],'State')
        }
    
    def create(self, cr, uid, vals, context=None):
        vals.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'direct.bank.expense'),
            })
        return super(direct_bank_expense, self).create(cr, uid, vals, context)
    
    _defaults = {
        'state':'draft',
        'rdate':lambda *a: time.strftime('%Y-%m-%d'),
	'user_id': lambda obj, cr, uid, context: uid,
        }
            
direct_bank_expense()

class direct_bank_expense_lines(osv.osv):
    _name = 'direct.bank.expense.lines'
    _description = "Distribution Lines"
    _columns = {
        'dbe_id':fields.many2one('direct.bank.expense','Distribution ID', ondelete='cascade'),
        'account_id':fields.many2one('account.analytic.account','Account'),
        'amount':fields.float('Amount'),
        'remarks':fields.char('Remarks',100),
        }
    
direct_bank_expense_lines()

class dbe(osv.osv):
    _inherit = 'direct.bank.expense'
    _columns = {
        'distribution_ids':fields.one2many('direct.bank.expense.lines','dbe_id','Distribution Lines'),
        }
    
    def distribute(self, cr, uid, ids, context=None):
        user_id = uid
        user_read = self.pool.get('res.users').read(cr, uid, user_id, ['company_id'])
        company_read = self.pool.get('res.company').read(cr, uid, user_read['company_id'][0],['currency_id','contributions_acct','donations','bank_charge'])
        
        comp_curr = company_read['currency_id'][0]
        rate = False
        currency = False
        for dbe in self.read(cr, uid, ids, context=None):
            bank_read = self.pool.get('res.partner.bank').read(cr, uid, dbe['bank_id'][0], context=None)
            journal_id = bank_read['journal_id'][0]
            period_search = self.pool.get('account.period').search(cr, uid, [('date_start','<=',dbe['rdate']),('date_stop','>=',dbe['rdate'])],limit=1)
            period_id = period_search[0]
            if bank_read['currency_id'][0]!=comp_curr:
                curr_read = self.pool.get('res.currency').read(cr, uid, bank_read['currency_id'][0],['rate'])
                currency = bank_read['currency_id'][0]
                rate = curr_read['rate']
            elif bank_read['currency_id'][0]==comp_curr:
                currency= bank_read['currency_id'][0]
                rate = 1.00
            move = {
                'journal_id':journal_id,
                'period_id':period_id,
                'date':dbe['rdate'],
                'ref':dbe['name'],
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            total_distribution = False
            total_contribution = False
            curr_distribution = False
            curr_contribution = False
            for dbel in dbe['distribution_ids']:
                dbel_read = self.pool.get('direct.bank.expense.lines').read(cr, uid, dbel, context=None)
                account_read = self.pool.get('account.analytic.account').read(cr, uid, dbel_read['account_id'][0],['normal_account'])
                distribution_amt = dbel_read['amount'] / rate
                amount = "%.2f" % distribution_amt
                distribution_amt = float(amount)
                curr_distribution +=distribution_amt            
                total_distribution += dbel_read['amount']
                name = dbel_read['remarks']
                move_line = {
                        'name':name,
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':account_read['normal_account'][0],
                        'debit':distribution_amt,                        
                        'date':dbe['rdate'],
                        'ref':dbe['name'],
                        'move_id':move_id,
                        'analytic_account_id':dbel_read['account_id'][0],
                        'amount_currency':dbel_read['amount'],
                        'currency_id':currency,
                        }
                self.pool.get('account.move.line').create(cr, uid, move_line)
            if total_distribution != dbe['amount']:
                raise osv.except_osv(_('Error!'), _('ERROR CODE - ERR-016: Total received amount is not equal to the total amount to be distributed!'))
            elif total_distribution== dbe['amount']:
                move_line = {
                        'name':dbe['name'],
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':bank_read['account_id'][0],
                        'credit':curr_distribution,                        
                        'date':dbe['rdate'],
                        'ref':dbe['name'],
                        'move_id':move_id,
                        'amount_currency':total_distribution,
                        'currency_id':currency,
                        }
                self.pool.get('account.move.line').create(cr, uid, move_line)
                #self.pool.get('account.move').post(cr, uid, [move_id])
                self.write(cr, uid, ids, {'state':'distributed','move_id':move_id})
        return True
dbe()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,
