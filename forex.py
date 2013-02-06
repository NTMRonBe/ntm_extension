
import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _

class forex_transaction(osv.osv):
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    def _get_journal(self, cr, uid, context=None):
        if context is None: context = {}
        journal_pool = self.pool.get('account.journal')
        if context.get('journal_id', False):
            return context.get('journal_id')
        if not context.get('journal_id', False) and context.get('search_default_journal_id', False):
            return context.get('search_default_journal_id')

        ttype = context.get('type', 'general')
        res = journal_pool.search(cr, uid, [('type', '=', ttype)])
        return res and res[0] or False
    
    _name = "forex.transaction"
    _description = "Forex Transaction"
    _columns = {
            'currency_one':fields.many2one('res.currency', 'Currency 1'),
            'currency_two':fields.many2one('res.currency','Currency 2'),
            'bank_account1_id':fields.many2one('account.account', "Bank Account 1"),
            'bank_account2_id':fields.many2one('account.account', "Bank Account 2"),
            'amount_currency1':fields.float('Amount'),
            'amount_currency2':fields.float('Amount', readonly=True),
            'rate':fields.float('Rate'),
            'journal_id':fields.many2one('account.journal', 'Journal', required=True, readonly=True, states={'draft':[('readonly',False)]}),
            'period_id':fields.many2one('account.period','Period'),
            'transact_date':fields.date('Transaction Date'),
            'state': fields.selection([
            ('draft','Draft'),
            ('post','Posted'),
            ],'State', select=True),
        }
    _defaults={
               'transact_date': lambda *a: time.strftime('%Y-%m-%d'),
               'state':'draft',
               'period_id':_get_period,
               }
    def create_exchange(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        exchange_fields = ['amount_currency1','rate',
                           'transact_date','currency_one',
                           'currency_two','bank_account1_id',
                           'bank_account2_id','journal_id','period_id']
        for trans in self.read(cr, uid, ids, exchange_fields):
            amount1=trans['amount_currency1']
            rate=trans['rate']
            date=trans['transact_date']
            curr1 = self.pool.get('res.currency').read(cr, uid, trans['currency_one'][0],['name'])
            curr2 = self.pool.get('res.currency').read(cr, uid, trans['currency_two'][0],['name'])
            comp_curr = self.pool.get('account.account').read(cr, uid, trans['bank_account1_id'][0],['company_currency_id'])
            amount2 = amount1 * rate 
            transaction_name = "Conversion from "+curr1['name']+" to "+curr2['name']
            move = {
                'name': transaction_name,
                'journal_id': trans['journal_id'][0],
                'date': trans['transact_date'],
                'period_id': trans['period_id'][0],
            }
            move_id = move_pool.create(cr, uid, move)
            if trans['currency_one'][0]==comp_curr['company_currency_id'][0]:
                move_line = {
                    'name': transaction_name or '/',
                    'credit': trans['amount_currency1'],
                    'debit': 0.00,
                    'account_id': trans['bank_account1_id'][0],
                    'move_id': move_id,
                    'journal_id': trans['journal_id'][0],
                    'date': trans['transact_date'],
                    'period_id': trans['period_id'][0],
                }
                move_line_pool.create(cr, uid, move_line)
                move_line = {
                    'name': transaction_name or '/',
                    'debit': trans['amount_currency1'],
                    'credit': 0.00,
                    'account_id': trans['bank_account2_id'][0],
                    'move_id': move_id,
                    'journal_id': trans['journal_id'][0],
                    'date': trans['transact_date'],
                    'period_id': trans['period_id'][0],
                    'currency_id':trans['currency_two'][0],
                    'amount_currency':amount2,
                }
                move_line_pool.create(cr, uid, move_line)
            elif trans['currency_one'][0]!=comp_curr['company_currency_id'][0]:
                move_line = {
                    'name': transaction_name or '/',
                    'debit': amount2,
                    'credit': 0.00,
                    'account_id': trans['bank_account2_id'][0],
                    'move_id': move_id,
                    'journal_id': trans['journal_id'][0],
                    'date': trans['transact_date'],
                    'period_id': trans['period_id'][0],
                }
                move_line_pool.create(cr, uid, move_line)
                move_line = {
                    'name': transaction_name or '/',
                    'credit': amount2,
                    'debit': 0.00,
                    'account_id': trans['bank_account1_id'][0],
                    'move_id': move_id,
                    'journal_id': trans['journal_id'][0],
                    'date': trans['transact_date'],
                    'period_id': trans['period_id'][0],
                    'currency_id':trans['currency_one'][0],
                    'amount_currency':amount1,
                }
                move_line_pool.create(cr, uid, move_line)
            move_pool.post(cr, uid, [move_id], context={})
            self.write(cr, uid, ids, {'amount_currency2':amount2,'state':'post'})
            
        return True
    def on_change_act1(self, cr, uid, ids, bank_account1_id=False):
        result = {}
        currency_id=0
        if bank_account1_id:
            account = self.pool.get('account.account').browse(cr, uid, bank_account1_id)
            if account.currency_id:
                currency_id = account.currency_id.id
            elif not account.currency_id:
                currency_id = account.company_currency_id.id
            result = {'value':{
                    'currency_one':currency_id,
                      }
                }
        return result
    
    def on_change_act2(self, cr, uid, ids, bank_account2_id=False):
        result = {}
        currency_id=0
        if bank_account2_id:
            account = self.pool.get('account.account').browse(cr, uid, bank_account2_id)
            if account.currency_id:
                currency_id = account.currency_id.id
            elif not account.currency_id:
                currency_id = account.company_currency_id.id
            result = {'value':{
                    'currency_two':currency_id,
                      }
                }
        return result
    
forex_transaction()