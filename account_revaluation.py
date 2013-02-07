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
                                  ('data_fetched','Primary Data Fetched'),
                                  ('postings_fetched','Postings Fetched'),
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
            for curr_ids in curr_lists:
                cur_ids = arc_pool.read(cr, uid, curr_ids,['currency_id'])
                currency = cur_ids['currency_id'][0]
                acc_lists = ara_pool.search (cr, uid, [('period_close_id','=',period_close_id)])
                for acc_ids in acc_lists:
                    acc_id = ara_pool.read(cr, uid, acc_ids,[('account_id')])
                    acc_id = acc_id['account_id'][0] 
                    aml_search = aml_pool.search(cr, uid, [('period_id','=',period_id), ('account_id','=',acc_id),('currency_id','=',currency)])
                    for aml_id in aml_search:
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
                for aml_id in aml_search:
                    aml_reader = aml_pool.read(cr, uid, aml_id,['debit','credit'])
                    debit += aml_reader['debit']
                    credit += aml_reader['credit']
                balance = debit - credit
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
            netsvc.Logger().notifyChannel("aml_search", netsvc.LOG_INFO, ' '+str(aml_search))
            for aml_ids in aml_search:
                record = pool('account.move.line').read(cr, uid, aml_ids,['currency_id'])
                currency_id = record['currency_id'][0]
                netsvc.Logger().notifyChannel("curr_id", netsvc.LOG_INFO, ' '+str(currency_id))
                if not currency_id in currency_lists:
                    wr=0.00
                    a1 = 0.00
                    a2 = 0.00
                    a3 = 0.00
                    a4 = 0.00
                    currency_lists.append(currency_id)
                    netsvc.Logger().notifyChannel("curr_list", netsvc.LOG_INFO, ' '+str(currency_lists))
                    netsvc.Logger().notifyChannel("period_id", netsvc.LOG_INFO, ' '+str(period_id))
                    netsvc.Logger().notifyChannel("comp_currency_id", netsvc.LOG_INFO, ' '+str(comp_currency_id))
                    netsvc.Logger().notifyChannel("currency_id", netsvc.LOG_INFO, ' '+str(currency_id))
                    forex_trans = self.pool.get('forex.transaction').search(cr, uid, [('period_id','=',period_id),('currency_one','=',comp_currency_id),('currency_two','=',currency_id)])
                    for forex in forex_trans:
                        trans = pool('forex.transaction').read(cr, uid, forex,['amount_currency1','amount_currency2'])
                        a1+=trans['amount_currency1']
                        a2+=trans['amount_currency2']
                        netsvc.Logger().notifyChannel("a1a2", netsvc.LOG_INFO, ' '+str(a1)+str(a2))
                    forex_trans = pool('forex.transaction').search(cr, uid, [('period_id','=',period_id),('currency_one','=',currency_id),('currency_two','=',comp_currency_id)])
                    for forex in forex_trans:
                        trans = pool('forex.transaction').read(cr, uid, forex,['amount_currency1','amount_currency2'])
                        a3+=trans['amount_currency1']
                        a4+=trans['amount_currency2']
                        netsvc.Logger().notifyChannel("a3a4", netsvc.LOG_INFO, ' '+str(a3)+str(a4))
                    a14 = a1 - a4
                    a23 = a2 - a3
                    wr = 0.00
                    if a14 < 0.00:
                        a14 = -1 * a14
                    if a23 < 0.00:
                        a23 = -1 * a23
                    if a23 > 0.00 and a14 > 0.00:
                        wr = a23 / a14
                        netsvc.Logger().notifyChannel("a14", netsvc.LOG_INFO, ' '+str(a14))
                        netsvc.Logger().notifyChannel("a23", netsvc.LOG_INFO, ' '+str(a23))
                        netsvc.Logger().notifyChannel("wr", netsvc.LOG_INFO, ' '+str(wr))
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
                curr_name = ""
                arc_reader = pool('account.revaluation.currencies').read(cr, uid, arc_ids, ['currency_id'])
                arc_id = arc_reader['currency_id'][0]
                curr_reader = pool('res.currency').read(cr, uid, arc_id,['name'])
                if curr_reader['name']=="PHP":
                    curr_name = "PHP"
                elif curr_reader['name']=="EUR":
                    curr_name = "EUR"
                ara_search = pool('account.revaluation.accounts').search(cr, uid, [('period_close_id','=',period_close_id)])
                for ara_ids in ara_search:
                    ara_reader = pool('account.revaluation.accounts').read(cr, uid, ara_ids,['account_id'])
                    ara_id = ara_reader['account_id'][0]
                    are_search = pool('account.revaluation.entries').search(cr, uid, [('period_close_id','=',period_close_id),('account_id','=',ara_id),('currency_id','=',arc_id)])
                    amount_currency = 0.00
                    for aml_ids in are_search:
                        are_reader = pool('account.revaluation.entries').read(cr, uid, aml_ids,['move_line_id'])
                        aml_id = are_reader['move_line_id'][0]
                        aml_reader = pool('account.move.line').read(cr, uid, aml_id,['amount_currency','debit'])
                        if aml_reader['debit']>0.00:
                            amount_currency+=aml_reader['amount_currency']
                        elif aml_reader['debit']==0.00:
                            amount_currency-=aml_reader['amount_currency']
                    if curr_name =="PHP":
                        pool('account.revaluation.accounts').write(cr, uid, ara_ids, {'php_post':amount_currency})
                    elif curr_name =="EUR":
                        pool('account.revaluation.accounts').write(cr, uid, ara_ids, {'eur_post':amount_currency})
            self.write(cr, uid, ids, {'state':'postings_fetched'})
        return True
    
    def compute_balap(self, cr, uid, ids, context=None):
        php_post_rate = 0.00
        eur_post_rate = 0.00
        php_reval_posting = 0.00
        eur_reval_posting = 0.00
        bal_ap = 0.00
        for arc_search in self.pool.get('account.revaluation.currencies').search(cr, uid, [('period_close_id','=',ids),('currency_id.name','ilike','PHP')]):
            arc_reader = self.pool.get('account.revaluation.currencies').read(cr, uid, arc_search, ['post_rate'])
            netsvc.Logger().notifyChannel("post_rate", netsvc.LOG_INFO, ' '+str(arc_reader['post_rate']))
            php_post_rate = arc_reader['post_rate']
        for arc_search in self.pool.get('account.revaluation.currencies').search(cr, uid, [('period_close_id','=',ids),('currency_id.name','ilike','EUR')]):
            arc_reader = self.pool.get('account.revaluation.currencies').read(cr, uid, arc_search, ['post_rate'])
            eur_post_rate = arc_reader['post_rate']  
        fields = ['account_id','bal_beg','php_post','eur_post']
        for acc_search in self.pool.get('account.revaluation.accounts').search(cr, uid, [('period_close_id','=',ids)]):
            acc_reader = self.pool.get('account.revaluation.accounts').read(cr, uid, acc_search,fields)
            php_reval_posting = acc_reader['php_post'] / php_post_rate
            eur_reval_posting = acc_reader['eur_post'] / eur_post_rate
            bal_ap = acc_reader['bal_beg'] + php_reval_posting + eur_reval_posting
            self.pool.get('account.revaluation.accounts' ).write(cr, uid, acc_search, {'bal_ap':bal_ap})
        for are_search in self.pool.get('account.revaluation.entries').search(cr, uid, [('period_close_id','=',ids),('currency_id.name','ilike','PHP')]):
            are_reader = self.pool.get('account.revaluation.entries').read(cr, uid, are_search,[''])
            
        return True
                
    
account_revaluation()

class account_revaluation_currencies(osv.osv):
    _name = 'account.revaluation.currencies'
    _columns = {
        'currency_id':fields.many2one('res.currency', "Currency"),
        'weighted_rate':fields.float("Weighted Rate",digits_compute=dp.get_precision('Account')),
        'start_rate':fields.float("Start Rate",digits_compute=dp.get_precision('Account')),
        'post_rate':fields.float("Post Rate",digits_compute=dp.get_precision('Account')),
        'end_rate':fields.float("End Rate",digits_compute=dp.get_precision('Account')),
        'period_close_id':fields.many2one('account.revaluation'),
    }
account_revaluation_currencies()

class account_revaluation_accounts(osv.osv):
    _name = 'account.revaluation.accounts'
    _columns = {
        'account_id':fields.many2one('account.account','Account'),
        'bal_beg':fields.float('Beginning Balance',digits_compute=dp.get_precision('Account')),
        'bal_ap':fields.float('Balance AP',digits_compute=dp.get_precision('Account')),
        'period_close_id':fields.many2one('account.revaluation'),
        'php_post':fields.float('PHP Postings',digits_compute=dp.get_precision('Account')),
        'eur_post':fields.float('EUR Postings',digits_compute=dp.get_precision('Account')),
        }
account_revaluation_accounts()

class account_revaluation_entries(osv.osv):
    _name = 'account.revaluation.entries'
    _columns = {
        'move_line_id':fields.many2one('account.move.line','Journal Item'),
        'currency_id':fields.related('move_line_id','currency_id',type='many2one',relation='res.currency',store=True, string='Currency'),
        'account_id':fields.related('move_line_id','account_id',type='many2one',relation='account.account',store=True,string="Account"),
        'debit': fields.related('move_line_id', 'debit', type="float", string="Debit", store=True,digits_compute=dp.get_precision('Account')),
        'credit': fields.related('move_line_id', 'credit', type="float", string="Credit", store=True,digits_compute=dp.get_precision('Account')),
        'amount_currency': fields.related('move_line_id', 'amount_currency', type="float", string="Amount Currency", store=True,digits_compute=dp.get_precision('Account')),
        'post_rate': fields.related('move_line_id', 'post_rate', type="float", string="Post Rate", store=True,digits_compute=dp.get_precision('Account')),
        'br_debit': fields.related('move_line_id', 'br_debit', type="float", string="After Revaluation Debit", store=True,digits_compute=dp.get_precision('Account')),
        'br_credit': fields.related('move_line_id', 'br_credit', type="float", string="After Revaluation Credit", store=True,digits_compute=dp.get_precision('Account')),
        'period_close_id':fields.many2one('account.revaluation'),
        }
account_revaluation_entries()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: