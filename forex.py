
import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
import decimal_precision as dp
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
            'name':fields.many2one('account.move','Name'),
            'move_ids': fields.related('name','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
            'currency_one':fields.many2one('res.currency', 'Currency From'),
            'currency_two':fields.many2one('res.currency','Currency Two'),
            'src':fields.many2one('res.partner.bank', "Source Bank"),
            'dest':fields.many2one('res.partner.bank', "Destination Bank"),
            'src_amount':fields.float('Amount'),
            'dest_amount':fields.float('Amount'),
            'rate':fields.float('Rate',digits=(16,6),readonly=True, help="Rate with respect to the company currency. 1 PHP= ###(Currency)"),
            'journal_id':fields.many2one('account.journal', 'Journal', required=True, readonly=True, states={'draft':[('readonly',False)]}),
            'period_id':fields.many2one('account.period','Period'),
            'transact_date':fields.date('Transaction Date'),
            'state': fields.selection([
            ('draft','Draft'),
            ('confirm','Confirm'),
            ('post','Posted'),
            ],'State', select=True),
        }
    _defaults={
               'transact_date': lambda *a: time.strftime('%Y-%m-%d'),
               'state':'draft',
               'period_id':_get_period,
               }
    
        
    def create_moves(self, cr, uid, ids, name, debit, credit, account_id, move_id, 
                     journal_id, date, period_id, currency_id, amount_currency, rate):
        move_line_pool = self.pool.get('account.move.line')
        move_line = {
                    'name': name or '/',
                    'debit': debit,
                    'credit': credit,
                    'account_id': account_id,
                    'move_id': move_id,
                    'journal_id': journal_id,
                    'date': date,
                    'period_id': period_id,
                    'currency_id':currency_id,
                    'amount_currency':amount_currency,
                    'post_rate':rate,
                }
        move_line_pool.create(cr, uid, move_line)
        return True
    
    
    def confirm(self, cr, uid, ids, context=None):
        for forex in self.read(cr, uid, ids, context=None):
            self.write(cr, uid, forex['id'],{'state':'confirm'})
        return True
    
    
    def post_exchange(self, cr, uid, ids, context=None):
        bank_pool = self.pool.get('res.partner.bank')
        acc_pool = self.pool.get('account.account')
        curr_pool = self.pool.get('res.currency')
        for exchange in self.read(cr, uid, ids, context=None):
            src_bank = exchange['src'][0]
            dest_bank = exchange['dest'][0]
            journal_id = exchange['journal_id'][0]
            period_id = exchange['period_id'][0]
            date = exchange['transact_date']
            curr_src = False
            curr_dest = False
            rate = False
            comp_curr_amt = False
            check_src_acc = bank_pool.read(cr, uid, src_bank,['account_id','transit_id'])
            check_dest_acc = bank_pool.read(cr, uid, dest_bank,['account_id','transit_id'])
            check_src_curr = acc_pool.read(cr, uid, check_src_acc['account_id'][0],['currency_id','company_currency_id'])
            check_dest_curr = acc_pool.read(cr, uid, check_dest_acc['account_id'][0],['currency_id','company_currency_id'])
            comp_curr = check_src_curr['company_currency_id'][0]
            if check_src_curr['currency_id']:
                curr_src = check_src_curr['currency_id'][0]
            if not check_src_curr['currency_id']:
                curr_src = check_src_curr['company_currency_id'][0]
            if check_dest_curr['currency_id']:
                curr_dest = check_dest_curr['currency_id'][0]
            if not check_dest_curr['currency_id']:
                curr_dest= check_dest_curr['company_currency_id'][0]
            src_amt = exchange['src_amount']
            dest_amt = exchange['dest_amount']
            if curr_src == comp_curr:
                rate = dest_amt / src_amt
                comp_curr_amt = src_amt
            if curr_dest == comp_curr:
                rate = src_amt / dest_amt
                comp_curr_amt = dest_amt
            netsvc.Logger().notifyChannel("src", netsvc.LOG_INFO, ' '+str(src_amt))
            netsvc.Logger().notifyChannel("dest", netsvc.LOG_INFO, ' '+str(dest_amt))
            netsvc.Logger().notifyChannel("rate", netsvc.LOG_INFO, ' '+str(rate))
            move= {
                'journal_id':journal_id,
                'period_id':period_id,
                'date':date,
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            #name, debit, credit, account_id, move_id, journal_id, date, period_id, currency_id, amount_currency, rate):
            ### Withdraw
            name = 'Withdraw from ' + check_src_acc['account_id'][1]
            move_line = {
                        'name':name,
                        'debit':0.00,
                        'credit':comp_curr_amt,
                        'account_id':check_src_acc['account_id'][0],
                        'move_id':move_id, 
                        'journal_id':journal_id, 
                        'date':date, 
                        'period_id':period_id, 
                        'currency_id':curr_src, 
                        'amount_currency':src_amt,
                        'post_rate':rate,
                        }
            
            self.pool.get('account.move.line').create(cr, uid, move_line)
            name = 'COH on ' + check_dest_acc['transit_id'][1]
            move_line = {
                        'name':name, 
                        'debit':comp_curr_amt,
                        'credit':0.00,
                        'account_id':check_src_acc['transit_id'][0],
                        'move_id':move_id, 
                        'journal_id':journal_id, 
                        'date':date, 
                        'period_id':period_id, 
                        'currency_id':curr_src, 
                        'amount_currency':src_amt,
                        'post_rate':rate,
                        }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            
            ### End of Withdraw
            
            ### Exchange
            name = 'Exchange of COH on' + check_dest_acc['transit_id'][1]
            move_line = {
                        'name':check_dest_acc['transit_id'][1],
                        'debit':comp_curr_amt,
                        'credit':0.00,
                        'account_id':check_dest_acc['transit_id'][0],
                        'move_id':move_id, 
                        'journal_id':journal_id, 
                        'date':date, 
                        'period_id':period_id, 
                        'currency_id':curr_dest, 
                        'amount_currency':dest_amt,
                        'post_rate':rate,
                        }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            name = 'Exchange of COH to ' + check_src_acc['transit_id'][1]
            move_line = {
                        'name':name,
                        'credit':comp_curr_amt,
                        'debit':0.00,
                        'account_id':check_src_acc['transit_id'][0],
                        'move_id':move_id, 
                        'journal_id':journal_id, 
                        'date':date, 
                        'period_id':period_id, 
                        'currency_id':curr_src, 
                        'amount_currency':src_amt,
                        'post_rate':rate,
                        }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            
            ### End of Exchange
            
            ### Deposit
            name = 'Deposit from COH on  ' + check_dest_acc['transit_id'][1]
            move_line = {
                        'name':name,
                        'credit':comp_curr_amt,
                        'debit':0.00,
                        'account_id':check_dest_acc['transit_id'][0],
                        'move_id':move_id, 
                        'journal_id':journal_id, 
                        'date':date, 
                        'period_id':period_id, 
                        'currency_id':curr_dest, 
                        'amount_currency':dest_amt,
                        'post_rate':rate,
                        }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            name = 'Deposit to ' + check_dest_acc['account_id'][1]
            move_line = {
                        'name':check_dest_acc['account_id'][1],
                        'debit':comp_curr_amt,
                        'credit':0.00,
                        'account_id':check_dest_acc['account_id'][0],
                        'move_id':move_id, 
                        'journal_id':journal_id, 
                        'date':date, 
                        'period_id':period_id, 
                        'currency_id':curr_dest, 
                        'amount_currency':dest_amt,
                        'post_rate':rate,
                        }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            self.pool.get('account.move').post(cr, uid, [move_id], context={})
            self.write(cr, uid, ids, {'rate':rate,'state':'post','name':move_id})
        return True
    
   
    def create_exchange(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        exchange_fields = ['amount_currency1','amount_currency2',
                           'transact_date','currency_one',
                           'currency_two','bank_account1_id',
                           'bank_account2_id','journal_id','period_id']
        for trans in self.read(cr, uid, ids, exchange_fields):
            amount1=trans['amount_currency1']
            amount2=trans['amount_currency2']
            date=trans['transact_date']
            curr1 = self.pool.get('res.currency').read(cr, uid, trans['currency_one'][0],['name'])
            curr2 = self.pool.get('res.currency').read(cr, uid, trans['currency_two'][0],['name'])
            comp_curr = self.pool.get('account.account').read(cr, uid, trans['bank_account1_id'][0],['company_currency_id'])
            if trans['currency_one'][0] == comp_curr['company_currency_id'][0]: 
                rate = amount2/amount1
            elif trans['currency_two'][0] == comp_curr['company_currency_id'][0]: 
                rate = amount1/amount2
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
                    'post_rate':rate,
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
                    'post_rate':rate,
                }
                move_line_pool.create(cr, uid, move_line)
            move_pool.post(cr, uid, [move_id], context={})
            self.write(cr, uid, ids, {'rate':rate,'state':'post'})
            
        return True
    def on_change_act1(self, cr, uid, ids, src=False):
        result = {}
        currency_id=0
        if src:
            account = self.pool.get('account.account').browse(cr, uid, src)
            if account.currency_id:
                currency_id = account.currency_id.id
            elif not account.currency_id:
                currency_id = account.company_currency_id.id
            result = {'value':{
                    'currency_one':currency_id,
                      }
                }
        return result
    
    def on_change_act2(self, cr, uid, ids, dest=False):
        result = {}
        currency_id=0
        if dest:
            account = self.pool.get('account.account').browse(cr, uid, dest)
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