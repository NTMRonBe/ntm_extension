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
        'company_id':fields.related('period_id','company_id',type='many2one',relation='res.company',store=True,string="Company"),
        'comp_curr':fields.related('company_id','currency_id',type='many2one',relation='res.currency',store=True,string="Company Currency"),
        'comp_curr_beg_bal':fields.float('Beginning Balance'),
        'currency_ids':fields.one2many('account.revaluation.currencies','period_close_id','Currencies', ondelete="cascade"),
        'state':fields.selection([
                                  ('draft','Draft'),
                                  ('data_fetched','Primary Data Fetched'),
                                  ('balap_computed','Balance Computed'),
                                  ('test_reval','Revaluation Checked'),
                                  ('verify','Verify'),
                                  ], 'State'),
        'line_ids':fields.one2many('account.revaluation.entries','period_close_id','Journal Items', ondelete="cascade"),
        'gain_loss_ids':fields.one2many('account.revaluation.gain.loss','period_close_id','Gain/Loss Accounts', ondelete="cascade"),
        'account_ids':fields.one2many('account.revaluation.accounts','period_close_id','PR Accounts', ondelete="cascade"),
    }
    _defaults = {
            'state':'draft',
            }
    
    def reval_entries(self, cr, uid, ids, context=None):
    	for reval in self.read(cr, uid, ids, ['id']):
    		period_close_id = reval['id']
    		for are_search in self.pool.get('account.revaluation.entries').search(cr, uid, [('period_close_id','=',period_close_id)]):
    			post_rate=0.00
    			are_fields = ['amount_currency','currency_id']
    			are_reader = self.pool.get('account.revaluation.entries').read(cr, uid, are_search,are_fields)
    			for arc_search in self.pool.get('account.revaluation.currencies').search(cr, uid,[('currency_id','=',are_reader['currency_id'][0]),('period_close_id','=',period_close_id)]):
    				arc_reader = self.pool.get('account.revaluation.currencies').read(cr, uid, arc_search,['post_rate'])
    				post_rate = arc_reader['post_rate']
    				reval_amount = are_reader['amount_currency'] / post_rate
    				self.pool.get('account.revaluation.entries').write(cr, uid, are_search,{'reval_amount':reval_amount})
    		self.write(cr, uid, ids, {'state':'test_reval'})
    	return True
 
    def get_move_lines(self,cr, uid, ids, context=None):
        aml_pool = self.pool.get('account.move.line')
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
                    aml_search = aml_pool.search(cr, uid, [('period_id','=',period_id), ('account_id','=',acc_id),('currency_id','=',currency),('name','not like','Conversion')], order= 'account_id asc')
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
        arc_pool = self.pool.get('account.revaluation.currencies')
        ara_pool = self.pool.get('account.revaluation.accounts')
        period_pool = self.pool.get('account.period')
        for reval in self.read(cr, uid, ids, ['period_id','id']):
            period_close_id = reval['id']
            period_id = reval['period_id'][0]
            per_id = period_pool.read(cr, uid, period_id,['date_start','date_stop'])
            date_start = per_id['date_start']
            acc_search = acc_pool.search(cr, uid, [('is_pr','=','True')])
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
        self.check_currencies(cr, uid, ids, context=context)
        self.get_account(cr, uid, ids, context=context)
        self.get_move_lines(cr, uid, ids, context=context)
        self.get_currency_beg_bal(cr, uid, ids, context=context)
        self.get_gain_loss_accounts(cr, uid, ids, context=context)
        return True
    def get_currency_beg_bal(self,cr, uid, ids, context=None):
        aml_pool = self.pool.get('account.move.line')
        arc_pool = self.pool.get('account.revaluation.currencies')
        period_pool = self.pool.get('account.period')
        for reval in self.read(cr, uid, ids, ['period_id','id']):
            period_close_id = reval['id']
            period_id = reval['period_id'][0]
            per_id = period_pool.read(cr, uid, period_id,['date_start','date_stop'])
            date_start = per_id['date_start']
            arc_search = arc_pool.search(cr, uid, [('period_close_id','=',period_close_id)])
            for arc_id in arc_search:
                arc_reader = arc_pool.read(cr, uid, arc_id, ['currency_id'])
                acc_id = arc_reader['currency_id'][0]
                aml_search = aml_pool.search(cr, uid,[('account_id.is_pr','=',False),('account_id.type','=','liquidity'),('date','<',date_start),('currency_id','=',acc_id)])
                balance = 0.00
                for aml_id in aml_search:
                    aml_reader = aml_pool.read(cr, uid, aml_id,['amount_currency'])
                    balance = aml_reader['amount_currency']
                values = {
                    'beg_bal':balance,
                    'ap_bal':balance
                    }
                arc_pool.write(cr, uid, arc_id, values)
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
                    forex_trans = self.pool.get('forex.transaction').search(cr, uid, [('period_id','=',period_id),('currency_one','=',comp_currency_id),('currency_two','=',currency_id)])
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
    def check_currencies(self, cr, uid, ids, context=None):
    	for reval in self.read(cr, uid, ids,['id']):
    		period_close_id=reval['id']
    		for arc_search in self.pool.get('account.revaluation.currencies').search(cr, uid,[('period_close_id','=',period_close_id)]):
    			arc_fields = ['start_rate','weighted_rate','post_rate','end_rate']
    			arc_read = self.pool.get('account.revaluation.currencies').read(cr, uid, arc_search,arc_fields)
    			if arc_read['weighted_rate']==0.00:
    				self.pool.get('account.revaluation.currencies').write(cr, uid, arc_search,{'post_rate':arc_read['start_rate'],'end_rate':arc_read['start_rate'],'weighted_rate':arc_read['start_rate']})
    			elif arc_read['weighted_rate']!=0.00:
    				continue
    	return True
    def compute_balap(self, cr, uid, ids, context=None):
        for reval in self.read(cr, uid, ids,['period_id','id','comp_curr_beg_bal']):
            period_close_id = reval['id']
            period_id = reval['period_id'][0]
            comp_curr_beg_bal = reval['comp_curr_beg_bal']
            for ara_search in self.pool.get('account.revaluation.accounts').search(cr, uid, [('period_close_id','=',period_close_id)]):
                ara_fields = ['bal_beg','bal_end','id','account_id']
                ara_read = self.pool.get('account.revaluation.accounts').read(cr, uid, ara_search,ara_fields)
                ara_bal_beg = ara_read['bal_beg']
                ara_bal_end = ara_read['bal_end']
                ara_id = ara_read['id']
                #### Account Revaluation Currencies Variables
                arc_start_rate = 0.00
                arc_weighted_rate = 0.00
                arc_post_rate = 0.00
                arc_beg_bal = 0.00
                arc_ap_bal = 0.00
                for are_search in self.pool.get('account.revaluation.entries').search(cr, uid, [('period_close_id','=',period_close_id),('account_id','=',ara_read['account_id'][0])]):
                    are_fields = ['currency_id','amount_currency','account_id']
                    are_read = self.pool.get('account.revaluation.entries').read(cr, uid, are_search,are_fields)
                    ara_recheck = self.pool.get('account.revaluation.accounts').read(cr, uid, ara_search,ara_fields)
                    for arc_search in self.pool.get('account.revaluation.currencies').search(cr, uid,[('currency_id','=',are_read['currency_id'][0]),('period_close_id','=',period_close_id)]):
                        arc_fields = ['start_rate','weighted_rate','post_rate','beg_bal','ap_bal']
                        arc_read = self.pool.get('account.revaluation.currencies').read(cr, uid, arc_search,arc_fields)
                        arc_start_rate = arc_read['start_rate']
                        arc_weighted_rate = arc_read['weighted_rate']
                        arc_post_rate = arc_read['post_rate']
                        arc_beg_bal = arc_read['beg_bal']
                        arc_ap_bal = arc_read['ap_bal']
                    balance_ap = ara_bal_beg + (are_read['amount_currency'] / arc_weighted_rate)
                    #diff1 = bal_beg * (PHP_beg / sr) / (USD_beg + PHP_beg / sr) * (sr / wr - 1)
                    diff1 = ara_bal_beg * (arc_beg_bal/arc_start_rate) / (comp_curr_beg_bal + arc_beg_bal/arc_start_rate) * (arc_start_rate/arc_weighted_rate -1)
                    #diff2 = (bal_ap + diff1) * (PHP_ap / wr) / (USD_ap + PHP_ap / wr) * (wr / er - 1)
                    diff2 = (balance_ap+diff1) * (arc_ap_bal/arc_weighted_rate) / (comp_curr_beg_bal + arc_ap_bal/arc_weighted_rate) * (arc_weighted_rate / arc_post_rate - 1)      
                    diff = diff2 + diff1
                    ara_bal_end = diff + balance_ap
                    ara_bal_beg = ara_bal_end
                    self.pool.get('account.revaluation.accounts').write(cr, uid, ara_id,{'bal_end':ara_bal_end,'diff':diff,'bal_ap':balance_ap})
                    self.pool.get('account.revaluation.entries').write(cr, uid, are_search,{'bal_end':ara_bal_end,'diff':diff,'bal_ap':balance_ap})
            self.write(cr, uid, ids, {'state':'balap_computed'})
        return True
    
    def adjust_post_rate(self,cr, uid, ids, context=None):
        for reval in self.read(cr, uid, ids, ['id']):
            period_close_id = reval['id']
            for ara in self.pool.get('account.revaluation.accounts').search(cr, uid, [('period_close_id','=',period_close_id)]):
                values = {
                    'bal_ap':0.00,
                    'diff':0.00,
                    'bal_end':0.00,
                    }
                self.pool.get('account.revaluation.accounts').write(cr, uid, ara, values)
        self.compute_balap(cr, uid, ids)
        self.reval_entries(cr, uid, ids)
        return True
    
    def get_gain_loss_accounts(self, cr, uid, ids, context=None):
        for reval in self.read(cr, uid, ids, ['id']):
            period_close_id=reval['id']
            for ara in self.pool.get('account.revaluation.accounts').search(cr, uid, [('period_close_id','=',period_close_id)]):
                ara_reader = self.pool.get('account.revaluation.accounts').read(cr, uid, ara,['account_id'])
                acc_pool = self.pool.get('account.account').read(cr, uid, ara_reader['account_id'][0],['gain_loss'] )
                gain_loss_acc = acc_pool['gain_loss'][0]
                values = {
                          'period_close_id':period_close_id,
                          'account_id':gain_loss_acc,
                          'rel_pr_account':ara_reader['account_id'][0],
                        }
                self.pool.get('account.revaluation.gain.loss').create(cr, uid, values)
        return True
    
    def check_gain_loss_accounts(self, cr, uid, ids, context=None):
        for reval in self.read(cr, uid, ids, ['id']):
            period_close_id = reval['id']
            for argl in self.pool.get('account.revaluation.gain.loss').search(cr, uid, [('period_close_id','=',period_close_id)]):
                argl_reader = self.pool.get('account.revaluation.gain.loss').read(cr, uid, argl,['rel_pr_account'])
                pr_acc = argl_reader['rel_pr_account'][0]
                gain_loss = 0.00
                for are in self.pool.get('account.revaluation.entries').search(cr, uid, [('period_close_id','=',period_close_id),('account_id','=',pr_acc)]):
                    are_reader = self.pool.get('account.revaluation.entries').read(cr, uid, are,['debit','credit','reval_amount'])
                    if are_reader['debit']==0.00:
                        gain_loss += (are_reader['credit'] + are_reader['reval_amount']) * -1
                        netsvc.Logger().notifyChannel("Debit", netsvc.LOG_INFO, ''+str(gain_loss))
                    elif are_reader['credit']==0.00:
                        gain_loss += are_reader['debit'] - are_reader['reval_amount']
                        netsvc.Logger().notifyChannel("Credit", netsvc.LOG_INFO, ''+str(gain_loss))
                self.pool.get('account.revaluation.gain.loss').write(cr, uid, argl,{'gain_loss':gain_loss})
        return True
    
account_revaluation()

class account_revaluation_currencies(osv.osv):
    _name = 'account.revaluation.currencies'
    _columns = {
        'currency_id':fields.many2one('res.currency', "Currency"),
        'weighted_rate':fields.float("Weighted Rate",digits_compute=dp.get_precision('Rates')),
        'start_rate':fields.float("Start Rate",digits_compute=dp.get_precision('Rates')),
        'post_rate':fields.float("Post Rate",digits_compute=dp.get_precision('Rates')),
        'end_rate':fields.float("End Rate",digits_compute=dp.get_precision('Rates')),
        'period_close_id':fields.many2one('account.revaluation'),
        'beg_bal':fields.float("Beginning Balance",digits_compute=dp.get_precision('Account')),
        'ap_bal':fields.float("After Posting Balance",digits_compute=dp.get_precision('Account')),
    }  
account_revaluation_currencies()

class account_revaluation_accounts(osv.osv):
    _name = 'account.revaluation.accounts'
    _columns = {
        'account_id':fields.many2one('account.account','Account'),
        'bal_beg':fields.float('Beginning Balance',digits_compute=dp.get_precision('Account')),
        'bal_ap':fields.float('Balance AP',digits_compute=dp.get_precision('Account')),
        'diff':fields.float('Diff'),
        'period_close_id':fields.many2one('account.revaluation'),
        'bal_end':fields.float('Ending Balance', digits_compute=dp.get_precision('Account')),
        }
account_revaluation_accounts()

class account_revaluation_entries(osv.osv):
    _name = 'account.revaluation.entries'
    _columns = {
        'move_line_id':fields.many2one('account.move.line','Journal Item'),
        'currency_id':fields.related('move_line_id','currency_id',type='many2one',relation='res.currency',store=True, string='Posting Currency'),
        'account_id':fields.related('move_line_id','account_id',type='many2one',relation='account.account',store=True,string="Account"),
        'debit': fields.related('move_line_id', 'debit', type="float", string="Debit", store=True,digits_compute=dp.get_precision('Account')),
        'credit': fields.related('move_line_id', 'credit', type="float", string="Credit", store=True,digits_compute=dp.get_precision('Account')),
        'amount_currency': fields.related('move_line_id', 'amount_currency', type="float", string="Posting Amount", store=True,digits_compute=dp.get_precision('Account')),
        'post_rate': fields.related('move_line_id', 'post_rate', type="float", string="Post Rate", store=True,digits_compute=dp.get_precision('Account')),
        'br_debit': fields.float("Revaluated Debit"),
        'br_credit': fields.float("Revaluated Credit"),
        'reval_amount':fields.float("Revaluated Amount"),
        'period_close_id':fields.many2one('account.revaluation'),
        'diff':fields.float('Diff'),
        'bal_ap':fields.float('Balance AP'),
        'bal_end':fields.float('Balance END'),
        }
account_revaluation_entries()

class account_revaluation_gain_loss(osv.osv):
    _name = 'account.revaluation.gain.loss'
    _columns = {
        'account_id':fields.many2one('account.account','Gain/Loss Account'),
        'rel_pr_account':fields.many2one('account.account','Related PR Account'),
        'period_close_id':fields.many2one('account.revaluation'),
        'gain_loss':fields.float('Gain/Loss Amount')
        }
account_revaluation_gain_loss()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: