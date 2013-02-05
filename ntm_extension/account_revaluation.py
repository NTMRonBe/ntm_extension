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
        are_pool = self.pool.get('account.revaluation.entries')
        for reval in self.read(cr, uid, ids,['period_id','id']):
            period_close_id = reval['id']
            period_id = reval['period_id'][0]
            aml_search = aml_pool.search(cr, uid, [('period_id','=',period_id)])
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
        for reval in self.read(cr, uid, ids, ['period_id','id']):
            period_close_id = reval['id']
            period_id = reval['period_id'][0]
            acc_search = acc_pool.search(cr, uid, [('pr','=','True')])
            for acc_id in acc_search:
                values = {
                    'account_id':acc_id,
                    'period_close_id':period_close_id,
                    }
                ara_pool.create(cr, uid, values)
                #aml_lines = aml_pool.search(cr, uid,[('account_id','=',acc_id)])
                #for aml_line in aml_lines:
                #    aml_read = aml_pool.read(cr, uid, aml_line,[('currency_id')])
                #    aml_curr_id = aml_read['currency_id'][0]
                #netsvc.Logger().notifyChannel("aml_id", netsvc.LOG_INFO, ' '+str(currency_lists))
        return True               
            
            
    def fetch_currencies(self, cr, uid, ids, context=None):
        apcnc_pool = self.pool.get('account.period.close.ntm.currencies')
        period_pool = self.pool.get('account.period')
        for form in self.read(cr, uid, ids, context=context):
            form_id = form['id']
            for id in context['active_ids']:
                for period_id in period_pool.browse(cr, uid, [id]):
                    period_id1 = period_id.id
                    comp_curr = period_id.company_id.currency_id.id
                    netsvc.Logger().notifyChannel("period_id", netsvc.LOG_INFO, ' '+str(period_id1))
                    date_start = period_id.date_start
                    netsvc.Logger().notifyChannel("period_id", netsvc.LOG_INFO, ' '+str(date_start))
                    date_start = "'"+date_start+"'"
                    date_stop = period_id.date_stop
                    netsvc.Logger().notifyChannel("period_id", netsvc.LOG_INFO, ' '+str(date_stop))
                    date_stop = "'"+date_stop+"'"
                    query = ("""select distinct(currency_id) from account_move_line where currency_id!=(select currency_id from res_company where id=(select company_id from res_users where id=%s)) and period_id=%s"""%(uid,period_id1))
                    netsvc.Logger().notifyChannel("query", netsvc.LOG_INFO, ' '+str(query))
                    cr.execute(query)
                    for t in cr.dictfetchall():
                        wr=0.00
                        currency_id = t['currency_id']
                        query = ("""select * from forex_transaction where period_id = %s and currency_one=%s and currency_two=%s"""%(period_id1,comp_curr,currency_id))
                        cr.execute(query)
                        amount_1 = 0.00
                        amount_2 = 0.00
                        for t in cr.dictfetchall():
                            amount_one = t['amount_currency1']
                            amount_two = t['amount_currency2']
                            amount_1 += amount_one
                            amount_2 += amount_two
                        amount_3 = 0.00
                        amount_4 = 0.00
                        query = ("""select * from forex_transaction where period_id = %s and currency_one=%s and currency_two=%s"""%(period_id1,currency_id,comp_curr))
                        cr.execute(query)
                        for t in cr.dictfetchall():
                            amount_one = t['amount_currency1']
                            amount_two = t['amount_currency2']
                            amount_3 += amount_one
                            amount_4 += amount_two
                        c1_amount = amount_1 - amount_4
                        c2_amount = amount_2 - amount_3
                        if c1_amount < 0.00:
                            c1_amount = -1.00 * c1_amount
                        if c2_amount < 0.00:
                            c2_amount = -1.00 * c2_amount
                        if c2_amount > 0.00 and c1_amount > 0.00:
                            wr = c2_amount / c1_amount
                        query = ("""select rate from res_currency_rate where currency_id=%s and name>=%s and name<=%s"""%(currency_id,date_start,date_stop))
                        cr.execute(query)
                        for t in cr.dictfetchall():
                            rate = t['rate']
                            currencies_list = {
                                'currency_id':currency_id,
                                'start_rate':rate,
                                'weighted_rate':wr,
                                'post_rate':wr,
                                'period_close_id':form_id,
                                }
                            apcnc_pool.create(cr, uid, currencies_list)
            self.write(cr, uid, ids, {'state':'compute'})
        return True
    
    def get_details(self, cr, uid, ids, context=None):
        self.get_currencies(cr, uid, ids, context=context)
        self.get_account(cr, uid, ids, context=context)
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
                #netsvc.Logger().notifyChannel("aml_id", netsvc.LOG_INFO, ' '+str(aml_ids))
                record = pool('account.move.line').read(cr, uid, aml_ids,['currency_id'])
                currency_id = record['currency_id'][0]
                #netsvc.Logger().notifyChannel("aml_id", netsvc.LOG_INFO, ' '+str(currency_lists))
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
                    if a14 < 0.00:
                        a14 = -1 * a14
                    rate_search = pool('res.currency.rate').search(cr, uid, [('currency_id','=',currency_id),'&',('name','>=',company['date_start']),('name','<=',company['date_stop'])])
                    rate_search = pool('res.currency.rate').read(cr, uid,rate_search[0],['rate'])
                    values = {
                        'currency_id':currency_id,
                        'start_rate':rate_search['rate'],
                        'period_close_id':period_close_id,
                        }
                    pool('account.revaluation.currencies').create(cr, uid, values)
            self.write(cr, uid, ids, {'state':'data_fetched'})
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