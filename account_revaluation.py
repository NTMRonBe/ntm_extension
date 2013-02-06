import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class account_revaluation(osv.osv):
    _name = "account.revaluation"
    _description = "Account Revaluations"
    _columns = {
        'period_id':fields.many2one('account.period','Period to close'),
        'currency_ids':fields.one2many('account.revaluation.currencies','period_close_id','Currencies', ondelete="cascade"),
        'state':fields.selection([
                                  ('draft','Draft'),
                                  ('data_fetched','Currencies Fetched'),
                                  ('verify','Verify'),
                                  ], 'State'),
        'line_ids':fields.one2many('account.revaluation.entries','period_close_id','Journal Items', ondelete="cascade"),
        'account_ids':fields.one2many('account.revaluation.accounts','period_close_id','PR Accounts', ondelete="cascade"),
    }
    _defaults = {
            'state':'draft',
            }
    
    def get_move_lines(self,cr, uid, ids, context=None):
        aml_pool = self.pool.get('account.move.line')
        curr_pool = self.pool.get('res.currency')
        acc_pool = self.pool.get('account.account')
        are_pool = self.pool.get('account.revaluation.entries')
        arc_pool = self.pool.get('account.revaluation.currencies')
        ara_pool = self.pool.get('account.revaluation.accounts')
        for reval in self.read(cr, uid, ids,['period_id','id']):
            period_close_id = reval['id']
            period_id = reval['period_id'][0]
            curr_lists = arc_pool.search(cr, uid, [('period_close_id','=',period_close_id)])
            netsvc.Logger().notifyChannel("1", netsvc.LOG_INFO, ' '+str('1'))
            for curr_ids in curr_lists:
                netsvc.Logger().notifyChannel("1", netsvc.LOG_INFO, ' '+str('2'))
                cur_ids = arc_pool.read(cr, uid, curr_ids,['currency_id'])
                currency = cur_ids['currency_id'][0]
                acc_lists = ara_pool.search (cr, uid, [('period_close_id','=',period_close_id)])
                for acc_ids in acc_lists:
                    netsvc.Logger().notifyChannel("1", netsvc.LOG_INFO, ' '+str('3'))
                    acc_id = ara_pool.read(cr, uid, acc_ids,[('account_id')])
                    acc_id = acc_id['account_id'][0] 
                    aml_search = aml_pool.search(cr, uid, [('period_id','=',period_id), ('account_id','=',acc_id),('currency_id','=',currency)])
                    for aml_id in aml_search:
                        netsvc.Logger().notifyChannel("1", netsvc.LOG_INFO, ' '+str('4'))
                        values={
                            'move_line_id':aml_id,
                            'period_close_id':period_close_id,
                            }
                        are_pool.create(cr, uid, values)
            self.write(cr, uid, ids, {'state':'data_fetched'})
        return True
    
    def get_account(self, cr, uid, ids, context=None):
        aml_pool = self.pool.get('account.move.line')
        acc_pool = self.pool.get('account.account')
        ara_pool = self.pool.get('account.revaluation.accounts')
        period_pool = self.pool.get('account.period')
        for reval in self.read(cr, uid, ids, ['period_id','id']):
            period_close_id = reval['id']
            period_id = reval['period_id'][0]
            per_id = period_pool.read(cr, uid, period_id,['date_start','date_stop'])
            date_start = per_id['date_start']
            acc_search = acc_pool.search(cr, uid, [('pr','=','True')])
            for acc_id in acc_search:
                aml_search = aml_pool.search(cr, uid,[('account_id','=',acc_id),('date','<',date_start)])
                debit = 0.00
                credit = 0.00
                balance = 0.00
                netsvc.Logger().notifyChannel("aml_search", netsvc.LOG_INFO, ' '+str(aml_search))
                for aml_id in aml_search:
                    netsvc.Logger().notifyChannel("aml_id", netsvc.LOG_INFO, ' '+str(aml_id))
                    aml_reader = aml_pool.read(cr, uid, aml_id,['debit','credit'])
                    debit += aml_reader['debit']
                    credit += aml_reader['credit']
                balance = debit - credit
                netsvc.Logger().notifyChannel("aml_search", netsvc.LOG_INFO, ' '+str(balance))
                values = {
                    'account_id':acc_id,
                    'period_close_id':period_close_id,
                    'bal_beg':balance,
                    }
                ara_pool.create(cr, uid, values)
        return True               
                      
    def get_details(self, cr, uid, ids, context=None):
        self.get_currencies(cr, uid, ids, context=context)
        self.get_account(cr, uid, ids, context=context)
        self.get_move_lines(cr, uid, ids, context=context)
        return True
    
    def get_currencies(self, cr, uid, ids, context=None):
        pool = self.pool.get
        for reval in self.read(cr, uid, ids, ['period_id','id']):
            period_close_id = reval['id']
            period_id = reval['period_id'][0]
            company = pool('account.period').read(cr, uid, period_id,['company_id','date_start','date_stop'])
            currency = pool('res.company').read(cr, uid, company['company_id'][0], ['currency_id'])
            comp_currency_id = currency['currency_id'][0]
            aml_search = pool('account.move.line').search(cr, uid, ['&','|',('period_id','=',period_id),('currency_id','!=',comp_currency_id),('currency_id','!=','')])
            currency_lists = []
            for aml_ids in aml_search:
                record = pool('account.move.line').read(cr, uid, aml_ids,['currency_id'])
                currency_id = record['currency_id'][0]
                if not currency_id in currency_lists:
                    wr=0.00
                    a1 = 0.00
                    a2 = 0.00
                    a3 = 0.00
                    a4 = 0.00
                    currency_lists.append(currency_id)
                    forex_trans = pool('forex.transaction').search(cr, uid, [('period_id','=',period_id),('currency_one','=',comp_currency_id),('currency_two','=',currency_id)])
                    for forex in forex_trans:
                        trans = pool('forex.transaction').read(cr, uid, forex,['amount_currency1','amount_currency2'])
                        a1+=trans['amount_currency1']
                        a2+=trans['amount_currency2']
                    forex_trans = pool('forex.transaction').search(cr, uid, [('period_id','=',period_id),('currency_one','=',currency_id),('currency_two','=',comp_currency_id)])
                    for forex in forex_trans:
                        trans = pool('forex.transaction').read(cr, uid, forex,['amount_currency1','amount_currency2'])
                        a3+=trans['amount_currency1']
                        a4+=trans['amount_currency2']
                    a14 = a1 - a4
                    a23 = a2 - a3
                    wr = 0.00
                    if a14 < 0.00:
                        a14 = -1 * a14
                    if a23 < 0.00:
                        a23 = -1 * a23
                    if a23 > 0.00 and a14 > 0.00:
                        wr = a23 / a14
                    rate_search = pool('res.currency.rate').search(cr, uid, [('currency_id','=',currency_id),'&',('name','>=',company['date_start']),('name','<=',company['date_stop'])])
                    rate_search = pool('res.currency.rate').read(cr, uid,rate_search[0],['rate'])
                    values = {
                        'currency_id':currency_id,
                        'start_rate':rate_search['rate'],
                        'period_close_id':period_close_id,
                        'weighted_rate':wr,
                        'post_rate':wr,
                        }
                    pool('account.revaluation.currencies').create(cr, uid, values)
        return True
    
    def compute_pool_accounts(self, cr, uid, ids, context=None):
        pool = self.pool.get
        for reval in self.read(cr, uid, ids, ['period_id','id']):
            period_close_id = reval['id']
            period_id = reval['period_id'][0]
            arc_search = pool('account.revaluation.currencies').search(cr, uid, [('period_close_id','=',period_close_id)])
            for arc_ids in arc_search:
                arc_reader = pool('account.revaluation.currencies').read(cr, uid, arc_ids, ['currency_id'])
                arc_id = arc_reader['currency_id'][0]
                are_search = pool('account.revaluation.entries').search(cr, uid, [('period_close_id','=',period_close_id)])
                amount_currency = 0.00
                for aml_ids in are_search:
                    are_reader = pool('account.revaluation.entries').read(cr, uid, aml_ids,['move_line_id'])
                    aml_id = are_reader['move_line_id'][0]
                    aml_reader = pool('account.move.line').read(cr, uid, aml_id,['amount_currency','debit'])
                    if aml_reader['debit']>0.00:
                        amount_currency+=aml_reader['amount_currency']
                    elif aml_reader['debit']==0.00:
                        amount_currency-=aml_reader['amount_currency']
                    netsvc.Logger().notifyChannel("aml_id", netsvc.LOG_INFO, ' '+str(amount_currency))
        return True
                
    
account_revaluation()

class account_revaluation_currencies(osv.osv):
    _name = 'account.revaluation.currencies'
    _columns = {
        'currency_id':fields.many2one('res.currency', "Currency"),
        'weighted_rate':fields.float("Weighted Rate"),
        'start_rate':fields.float("Start Rate"),
        'post_rate':fields.float("Post Rate"),
        'end_rate':fields.float("End Rate"),
        'period_close_id':fields.many2one('account.revaluation'),
    }
account_revaluation_currencies()

class account_revaluation_accounts(osv.osv):
    _name = 'account.revaluation.accounts'
    _columns = {
        'account_id':fields.many2one('account.account','Account'),
        'bal_beg':fields.float('Beginning Balance'),
        'currency_id':fields.many2one('res.currency', 'Currency'),
        'bal_ap':fields.float('Balance AP'),
        'period_close_id':fields.many2one('account.revaluation'),
        'php_post':fields.float('Php Postings'),
        'usd_post':fields.float('USD Postings'),
        'eur_post':fields.float('EUR Postings'),
        }
account_revaluation_accounts()

class account_revaluation_entries(osv.osv):
    _name = 'account.revaluation.entries'
    _columns = {
        'move_line_id':fields.many2one('account.move.line','Journal Item'),
        'debit': fields.related('move_line_id', 'debit', type="float", string="Debit", store=True),
        'credit': fields.related('move_line_id', 'credit', type="float", string="Credit", store=True),
        'post_rate': fields.related('move_line_id', 'post_rate', type="float", string="Post Rate", store=True),
        'br_debit': fields.related('move_line_id', 'br_debit', type="float", string="Before Revaluation Debit", store=True),
        'br_credit': fields.related('move_line_id', 'br_credit', type="float", string="Before Revaluation Credit", store=True),
        'period_close_id':fields.many2one('account.revaluation'),
        }
account_revaluation_entries()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: