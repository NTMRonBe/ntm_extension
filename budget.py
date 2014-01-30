import time
from osv import osv, fields, orm
import netsvc
import pooler
import datetime
import psycopg2
from tools.translate import _

class ntm_budget(osv.osv):
    _name = 'ntm.budget'
    _description = "Budget Management"
    _columns = {
        'year_id':fields.many2one('account.fiscalyear','Fiscal Year', required=True),
        'name':fields.char('Budget Name',size=64, required=True),
        'state':fields.selection([
                        ('draft','Draft'),
                        ('active','Active'),
                        ('closed','Closed'),
                        ],'State'),
        }
    
    _defaults = {
            'state':'draft',
            }
ntm_budget()

class ntm_budget_acc(osv.osv):
    _name = 'ntm.budget.acc'
    _description = "Accounts"
    _columns = {
        'name':fields.many2one('account.analytic.account','Analytic Account', required=True),
        'previous_actual':fields.float('Previous Actual'),
        'present_budget':fields.float('Present Budget'),
        'previous_budget':fields.float('Previous Budget'),
        'actual_amount':fields.float('Actual Amount'),
        'percentage':fields.float('Percentage', readonly=True),
        'income_id':fields.many2one('ntm.budget','Budget ID', ondelete='cascade'),
        'expense_id':fields.many2one('ntm.budget','Budget ID', ondelete='cascade'),        
        }
ntm_budget_acc()

class ntm_budget_acc_period(osv.osv):
    _name = 'ntm.budget.acc.period'
    _columns = {
        'name':fields.many2one('account.period','Period'),
        'actual':fields.float('Used', readonly=True),
        'acc_id':fields.many2one('ntm.budget.acc','Account', ondelete='cascade'),
        }
ntm_budget_acc_period()

class ntmba(osv.osv):
    _inherit = 'ntm.budget.acc'
    _columns = {
        'period_ids':fields.one2many('ntm.budget.acc.period','acc_id','Periods')
        }
ntmba()

class ntmb(osv.osv):
    _inherit = 'ntm.budget'
    _columns = {
        'income_ids':fields.one2many('ntm.budget.acc','income_id','Income Accounts'),
        'expense_ids':fields.one2many('ntm.budget.acc','expense_id','Expense Accounts'),
        }
    
    def activate(self, cr, uid, ids, context=None):
        for ntmb in self.read(cr, uid, ids, context=None):
            fiscal_id = ntmb['year_id'][0]
            fiscalRead = self.pool.get('account.fiscalyear').read(cr, uid, fiscal_id, ['period_ids'])
            periods = fiscalRead['period_ids']
            for incomeAcc in ntmb['income_ids']:
                for period in periods:
                    vals = {
                        'acc_id':incomeAcc,
                        'name':period,
                        }
                    self.pool.get('ntm.budget.acc.period').create(cr, uid, vals)
            for expenseAcc in ntmb['expense_ids']:
                for period in periods:
                    vals = {
                        'acc_id':expenseAcc,
                        'name':period,
                        }
                    self.pool.get('ntm.budget.acc.period').create(cr, uid, vals)
        return self.write(cr, uid, ids, {'state':'active'})
    
    def close(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state':'closed'})
    
    def update(self, cr, uid, ids, context=None):
        for ntmb in self.read(cr, uid, ids, context=None):
            fiscal_id = ntmb['year_id'][0]
            fiscalRead = self.pool.get('account.fiscalyear').read(cr, uid, fiscal_id, ['period_ids'])
            periods = fiscalRead['period_ids']
            for incomeAcc in ntmb['income_ids']:
                accRead = self.pool.get('ntm.budget.acc').read(cr, uid, incomeAcc, ['name'])
                account_id = accRead['name'][0]
                actual_amt = 0.00
                for period in periods:
                    periodRead = self.pool.get('account.period').read(cr, uid, period, ['date_start','date_stop'])
                    start = periodRead['date_start']
                    stop = periodRead['date_stop']
                    searchEntries = self.pool.get('account.analytic.line').search(cr, uid, [('date','<=',stop),('date','>=',start),('account_id','=',account_id)])
                    total_amount = 0.00
                    for entry in searchEntries:
                        entryRead=self.pool.get('account.analytic.line').read(cr, uid, entry, ['amount'])
                        total_amount +=entryRead['amount']
                    actual_amt += total_amount
                    searchPeriod = self.pool.get('ntm.budget.acc.period').search(cr, uid, [('name','=',period),('acc_id','=',incomeAcc)])
                    self.pool.get('ntm.budget.acc.period').write(cr, uid, searchPeriod[0], {'actual':total_amount})
                self.pool.get('ntm.budget.acc').write(cr, uid, incomeAcc, {'actual_amount':actual_amt})
            for expenseAcc in ntmb['expense_ids']:
                accRead = self.pool.get('ntm.budget.acc').read(cr, uid, expenseAcc, ['name'])
                account_id = accRead['name'][0]
                actual_amt = 0.00
                for period in periods:
                    periodRead = self.pool.get('account.period').read(cr, uid, period, ['date_start','date_stop'])
                    start = periodRead['date_start']
                    stop = periodRead['date_stop']
                    searchEntries = self.pool.get('account.analytic.line').search(cr, uid, [('date','<=',stop),('date','>=',start),('account_id','=',account_id)])
                    total_amount = 0.00
                    for entry in searchEntries:
                        entryRead=self.pool.get('account.analytic.line').read(cr, uid, entry, ['amount'])
                        total_amount +=entryRead['amount']
                    actual_amt += total_amount
                    searchPeriod = self.pool.get('ntm.budget.acc.period').search(cr, uid, [('name','=',period),('acc_id','=',expenseAcc)])
                    self.pool.get('ntm.budget.acc.period').write(cr, uid, searchPeriod[0], {'actual':total_amount})
                self.pool.get('ntm.budget.acc').write(cr, uid, expenseAcc, {'actual_amount':actual_amt})
        return True
ntmb()