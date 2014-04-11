
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
            'name':fields.related('move_id','name',type='char', size=64, string="Name", readonly=True),
            'move_id':fields.many2one('account.move','Move'),
            'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
            'src':fields.many2one('res.partner.bank', "Source Bank"),
            'dest':fields.many2one('res.partner.bank', "Destination Bank"),
            'src_amount':fields.float('Amount'),
            'dest_amount':fields.float('Amount'),
            'rate':fields.float('Rate',digits=(16,5),readonly=True, help="Rate with respect to the company currency. 1 PHP= ###(Currency)"),
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
            curr_name = False
            if check_src_curr['currency_id']:
                curr_src = check_src_curr['currency_id'][0]
            if not check_src_curr['currency_id']:
                curr_src = check_src_curr['company_currency_id'][0]
            if check_dest_curr['currency_id']:
                curr_dest = check_dest_curr['currency_id'][0]
                curr_name = check_dest_curr['currency_id'][1]
            if not check_dest_curr['currency_id']:
                curr_dest= check_dest_curr['company_currency_id'][0]
                curr_name = check_dest_curr['company_currency_id'][1]
            if curr_src==curr_dest:
                raise osv.except_osv(_('Error!'), _('FOREX-001: Exchanges with the same bank account currencies are not allowed!'))
            if exchange['src_amount'] <= 0.00 or exchange['dest_amount'] <= 0.00 :
                raise osv.except_osv(_('Error!'), _('FOREX-002: Zero amounts are not allowed!'))
            if not curr_src==curr_dest and exchange['src_amount'] > 0.00 or exchange['dest_amount'] > 0.00:
                src_amt = exchange['src_amount']
                dest_amt = exchange['dest_amount']
                if curr_src == comp_curr:
                    rate = dest_amt / src_amt
                    comp_curr_amt = src_amt
                if curr_dest == comp_curr:
                    rate = src_amt / dest_amt
                    comp_curr_amt = dest_amt
                move= {
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'date':date,
                    }
                move_id = self.pool.get('account.move').create(cr, uid, move)
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
                self.write(cr, uid, ids, {'rate':rate,'state':'post','move_id':move_id})
        return True
forex_transaction()