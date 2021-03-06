import time
from osv import osv, fields, orm
import netsvc
import pooler
from tools.translate import _
import decimal_precision as dp

class account_revaluation(osv.osv):
    
    def _get_journal(self, cr, uid, context=None):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        res = journal_obj.search(cr, uid, [('type', '=', 'arj')],limit=1)
        return res and res[0] or False

    _name = "account.revaluation"
    _description = "Account Revaluations"
    _columns = {
        'period_id':fields.many2one('account.period','Period to close'),
        'name':fields.date('Revaluation Date'),
        'src_exchange_ids':fields.many2many('forex.transaction','forex_reval_src_rel','forex_id','reval_id','Exchanges'),
        'dest_exchange_ids':fields.many2many('forex.transaction','forex_reval_dest_rel','forex_id','reval_id','Exchanges'),
        'state':fields.selection([
                                  ('draft','Draft'),
                                  ('revaluated','Revaluated'),
                                  ('verified', 'Verified'),
                                  ('validated','Validated'),
                                  ], 'State'),
        'comp_curr':fields.many2one('res.currency','Currency'),
        'comp_balbeg':fields.float('Beginning Balance'),
        'comp_balap':fields.float('Balance After Posting'),
        'second_balbeg':fields.float('Beginning Balance'),
        'second_balap':fields.float('Balance After Posting'),
        'second_curr':fields.many2one('res.currency','Currency'),
        'start_rate':fields.float('Start Rate',digits=(16,6)),
        'weighted_rate':fields.float('Weighted Rate',digits=(16,6)),
        'post_rate':fields.float('Post Rate',digits=(16,6)),
        'end_rate':fields.float('End Rate',digits=(16,6)),
        'pool_equivalent_beg_comp':fields.float('Pool Equivalent', digits_compute=dp.get_precision('Account')),
        'pool_equivalent_beg_second':fields.float('Pool Equivalent', digits_compute=dp.get_precision('Account')),
        'pool_equivalent_ap_comp':fields.float('Pool Equivalent', digits_compute=dp.get_precision('Account')),
        'pool_equivalent_ap_second':fields.float('Pool Equivalent', digits_compute=dp.get_precision('Account')),
        'pool_total_beg':fields.float('Pool Total', digits_compute=dp.get_precision('Account')),
        'pool_total_ap':fields.float('Pool Total', digits_compute=dp.get_precision('Account')),
        'portion_factor_beg_comp':fields.float('Portion Factor', digits=(16,6)),
        'portion_factor_beg_second':fields.float('Portion Factor', digits=(16,6)),
        'portion_factor_ap_comp':fields.float('Portion Factor', digits=(16,6)),
        'portion_factor_ap_second':fields.float('Portion Factor', digits=(16,6)),
        'rate_change_beg_comp':fields.float('Rate Change Factor', digits=(16,8)),
        'journal_id':fields.many2one('account.journal','Journal',),
        'rate_change_beg_second':fields.float('Rate Change Factor', digits=(16,8)),
        'rate_change_ap_comp':fields.float('Rate Change Factor', digits=(16,8)),
        'rate_change_ap_second':fields.float('Rate Change Factor', digits=(16,8)),
        'reval_beg':fields.float('Revaluation Factor',digits=(16,8)),
        'reval_ap':fields.float('Revaluation Factor', digits=(16,8)),
        'reval_log':fields.text('Revaluation Log', readonly=True),
    }
    
    def _get_exchanges_src(self, cr, uid, ids, context=None):
        period_read = self.pool.get('account.period').read(cr, uid, ids['default_period_id'],['company_id'])
        comp_read = self.pool.get('res.company').read(cr, uid, period_read['company_id'][0],['currency_id'])
        currency = comp_read['currency_id'][0]
        return self.pool.get('forex.transaction').search(cr, uid ,[('period_id','=',ids['default_period_id']),('src.currency_id','=',currency)])
    
    def _get_exchanges_dest(self, cr, uid, ids, context=None):
        period_read = self.pool.get('account.period').read(cr, uid, ids['default_period_id'],['company_id'])
        comp_read = self.pool.get('res.company').read(cr, uid, period_read['company_id'][0],['currency_id'])
        currency = comp_read['currency_id'][0]
        return self.pool.get('forex.transaction').search(cr, uid ,[('period_id','=',ids['default_period_id']),('dest.currency_id','=',currency)])
    
    def _get_start_rate(self, cr, uid, ids, context=None):
        curr_list = []
        curr = False
        period_read = self.pool.get('account.period').read(cr, uid, ids['default_period_id'],['company_id','date_start','date_stop'])
        comp_read = self.pool.get('res.company').read(cr, uid, period_read['company_id'][0],['currency_id'])
        exchanges = self.pool.get('forex.transaction').search(cr, uid, [('period_id','=',ids['default_period_id'])])
        for exchange in exchanges:
            exchange_read = self.pool.get('forex.transaction').browse(cr, uid, exchange)
            if exchange_read.src.currency_id.id==exchange_read.src.account_id.company_currency_id.id:
                if exchange_read.dest.currency_id.id not in curr_list:
                    curr_list.append(exchange_read.dest.currency_id.id)
            elif exchange_read.dest.currency_id.id==exchange_read.dest.account_id.company_currency_id.id:
                if exchange_read.src.currency_id.id not in curr_list:
                    curr_list.append(exchange_read.src.currency_id.id)
        if curr_list:
            curr = curr_list[0]
        elif not curr_list:
            curr=False
        rate_search = self.pool.get('res.currency.rate').search(cr, uid, [('currency_id','=',curr),
                                                                              ('name','>=',period_read['date_start']),
                                                                              ('name','<=',period_read['date_stop'])])
        if rate_search:
            rate_read = self.pool.get('res.currency.rate').read(cr, uid, rate_search[0],['rate'])
            return rate_read['rate']
    
    def _get_company_curr(self, cr, uid, ids, context=None):
        period_read = self.pool.get('account.period').read(cr, uid, ids['default_period_id'],['company_id'])
        comp_read = self.pool.get('res.company').read(cr, uid, period_read['company_id'][0],['currency_id'])
        return comp_read['currency_id'][0]
    
    def _get_secondary(self, cr, uid, ids, context=None):
        curr_list = []
        period_read = self.pool.get('account.period').read(cr, uid, ids['default_period_id'],['company_id'])
        comp_read = self.pool.get('res.company').read(cr, uid, period_read['company_id'][0],['currency_id'])
        exchanges = self.pool.get('forex.transaction').search(cr, uid, [('period_id','=',ids['default_period_id'])])
        for exchange in exchanges:
            exchange_read = self.pool.get('forex.transaction').browse(cr, uid, exchange)
            if exchange_read.src.currency_id.id==exchange_read.src.account_id.company_currency_id.id:
                if exchange_read.dest.currency_id.id not in curr_list:
                    curr_list.append(exchange_read.dest.currency_id.id)
            elif exchange_read.dest.currency_id.id==exchange_read.dest.account_id.company_currency_id.id:
                if exchange_read.src.currency_id.id not in curr_list:
                    curr_list.append(exchange_read.src.currency_id.id)
        if curr_list:
            return curr_list[0]
        elif not curr_list:
            return False
    
    def _get_secondary_balbeg(self, cr, uid, ids, context=None):
        curr_list = []
        period_read = self.pool.get('account.period').read(cr, uid, ids['default_period_id'],['company_id','date_start'])
        comp_read = self.pool.get('res.company').read(cr, uid, period_read['company_id'][0],['currency_id'])
        exchanges = self.pool.get('forex.transaction').search(cr, uid, [('period_id','=',ids['default_period_id'])])
        for exchange in exchanges:
            exchange_read = self.pool.get('forex.transaction').browse(cr, uid, exchange)
            if exchange_read.src.currency_id.id==exchange_read.src.account_id.company_currency_id.id:
                if exchange_read.dest.currency_id.id not in curr_list:
                    curr_list.append(exchange_read.dest.currency_id.id)
            elif exchange_read.dest.currency_id.id==exchange_read.dest.account_id.company_currency_id.id:
                if exchange_read.src.currency_id.id not in curr_list:
                    curr_list.append(exchange_read.src.currency_id.id)
        moves = self.pool.get('account.move.line').search(cr,uid, [('date','<',period_read['date_start']),
                                                                   ('account_id.currency_id','=',curr_list[0]),
                                                                   ('account_id.type','=','liquidity'),
                                                                   ('account_id.is_pr','=',False),
                                                                   ])
        balbeg = False
        for move in moves:
            move_read = self.pool.get('account.move.line').read(cr, uid, move, ['debit','credit','amount_currency'])
            if move_read['debit']!=0.00: 
                balbeg +=move_read['amount_currency']
            elif move_read['credit']!=0.00:
                balbeg -=move_read['amount_currency']
        if balbeg!=False:
            return balbeg
        elif balbeg==False:
            return False
    
    def _get_wr(self, cr, uid, ids, context=None):
        curr_list = []
        src_1 = False
        dest_1 = False
        src_2 = False
        dest_2 = False
        period_read = self.pool.get('account.period').read(cr, uid, ids['default_period_id'],['company_id'])
        comp_read = self.pool.get('res.company').read(cr, uid, period_read['company_id'][0],['currency_id'])
        exchanges = self.pool.get('forex.transaction').search(cr, uid, [('period_id','=',ids['default_period_id'])])
        for exchange in exchanges:
            exchange_read = self.pool.get('forex.transaction').browse(cr, uid, exchange)
            if exchange_read.src.currency_id.id==exchange_read.src.account_id.company_currency_id.id:
                src_1 +=exchange_read.src_amount
                dest_1 +=exchange_read.dest_amount
            elif exchange_read.dest.currency_id.id==exchange_read.dest.account_id.company_currency_id.id:
                src_2 +=exchange_read.src_amount
                dest_2 +=exchange_read.dest_amount
        start_rate = False
        total_1 = src_1 - dest_2
        total_2 = src_2 - dest_1
        if total_1 <0.00:
            total_1 = total_1 * -1
        if total_2 < 0.00:
            total_2 = total_2 * -1
        if total_1 ==0.00:
            return False
        if total_2 ==0.00:
            return False
        if total_2 != 0.00 and total_1 !=0.00:
            weighted = total_2 / total_1
            amount = "%.5f" % weighted
            weighted = float(amount)
            return weighted
    
    _defaults = {
            'state':'draft',
            'journal_id':_get_journal,
            'src_exchange_ids':_get_exchanges_src,
            'dest_exchange_ids':_get_exchanges_dest,
            'comp_curr':_get_company_curr,
            'name':lambda *a: time.strftime('%Y-%m-%d'),
            'second_curr':_get_secondary,
            'start_rate':_get_start_rate,
            'weighted_rate':_get_wr,
            'post_rate':_get_wr,
            'end_rate':_get_wr,
            'rate_change_beg_comp':1.00,
            'rate_change_ap_comp':1.00,
            }
    
    def fetch_accounts(self, cr, uid, ids, context=None):
        for reval in self.read(cr, uid, ids, context=None):
            logCheck = ''
            period_read = self.pool.get('account.period').read(cr, uid, reval['period_id'][0],['date_start','date_stop','company_id'])
            acc_search = self.pool.get('account.account').search(cr, uid, [('is_pr','=',True)])
            for reval_acc in reval['income_ids']:
                self.pool.get('account.revaluation.account').unlink(cr, uid, reval_acc)
            for reval_acc in reval['expense_ids']:
                self.pool.get('account.revaluation.account').unlink(cr, uid, reval_acc)
            for reval_acc in reval['equity_ids']:
                self.pool.get('account.revaluation.account').unlink(cr, uid, reval_acc)
            for reval_acc in reval['project_ids']:
                self.pool.get('account.revaluation.account').unlink(cr, uid, reval_acc)
            for reval_acc in reval['pat_ids']:
                self.pool.get('account.revaluation.account').unlink(cr, uid, reval_acc)
            for acc in acc_search:
                acc_read = self.pool.get('account.account').read(cr, uid, acc,['gain_loss'])
                gl_acc_id = False
                analytic_search = self.pool.get('account.analytic.account').search(cr, uid, [('normal_account','=',acc)])
                for analytic in analytic_search:
                    analyticRead = self.pool.get('account.analytic.account').read(cr, uid, analytic, ['ntm_type','normal_account','region_id', 'name'])
                    if analyticRead['ntm_type'] in ['income','expense','equity']:
                        regionRead = self.pool.get('region.config').read(cr, uid, analyticRead['region_id'][0],['gain_loss_acct'])
                        gl_acc_id = regionRead['gain_loss_acct'][0]
                    elif analyticRead['ntm_type'] not in ['income','expense']:
                        normalRead = self.pool.get('account.account').read(cr, uid,analyticRead['normal_account'][0],['gain_loss'])
                        gl_acc_id=normalRead['gain_loss'][0]
                    comp_bal_beg= False
                    comp_moves_search = self.pool.get('account.move.line').search(cr, uid, [('account_id','=',acc),
                                                                                            ('analytic_account_id','=',analytic),
                                                                                            ('date','<',period_read['date_start'])])
                    for comp_move in comp_moves_search:
                        comp_move_read = self.pool.get('account.move.line').read(cr, uid, comp_move, ['debit','credit'])
                        comp_bal_beg +=comp_move_read['debit']-comp_move_read['credit']
                    ending_moves_search = self.pool.get('account.move.line').search(cr, uid, [('account_id','=',acc),
                                                                                                ('analytic_account_id','=',analytic),
                                                                                                ('date','>=',period_read['date_start']),
                                                                                                ('date','<=',period_read['date_stop'])])
                    if comp_bal_beg !=0.00 or ending_moves_search:
                        ending_bal= False
                        posts_comp = False
                        posts_second = False
                        encoded_second = False
                        for ending_move in ending_moves_search:
                            ending_move_read = self.pool.get('account.move.line').read(cr, uid, ending_move, ['debit','amount_currency','credit','currency_id'])
                            if ending_move_read['currency_id'][0]==reval['comp_curr'][0]:
                                posts_comp += ending_move_read['debit'] - ending_move_read['credit']
                            elif ending_move_read['currency_id'][0]==reval['second_curr'][0]:
                                posts_second += ending_move_read['debit'] - ending_move_read['credit']
                                if ending_move_read['debit']==0.00:
                                    encoded_second-=ending_move_read['amount_currency']
                                elif ending_move_read['credit']==0.00:
                                    encoded_second+=ending_move_read['amount_currency']
                        ending_bal = posts_comp + posts_second + comp_bal_beg
                        adjusted_bal = encoded_second / reval['post_rate']
                        new_adjusted_bal = posts_comp + adjusted_bal
                        adjustment = ending_bal - new_adjusted_bal
                        vals = {
                            'account_id':acc,
                            'analytic_id':analytic,
                            'gainloss_account_id':gl_acc_id,
                            'period_close_id':reval['id'],
                            'adjustment':adjustment,
                            'comp_bal_beg':comp_bal_beg,
                            'bal_ap':ending_bal,
                            'state':'draft',
                            'ntm_type':analyticRead['ntm_type'],
                            }
                        self.pool.get('account.revaluation.account').create(cr, uid, vals)
                        logCheck = logCheck +'\n'+analyticRead['name']+ ' has been revaluated'
                    
                        self.write(cr, uid, ids, {'reval_log':logCheck})
        return self.get_computation_details(cr, uid, ids)
    
    def get_computation_details(self, cr, uid, ids, context=None):
        log2 = ''
        for reval in self.read(cr, uid, ids, context=None):
            period_read = self.pool.get('account.period').read(cr, uid, reval['period_id'][0],['date_start','date_stop'])
            moves = self.pool.get('account.move.line').search(cr,uid, [('date','<',period_read['date_start']),
                                                                       ('account_id.include_pool','=',True),
                                                                       ])
            balbegcomp = False
            balapcomp = False
            balbegsec = False
            balapsec = False
            for move in moves:
                move_read = self.pool.get('account.move.line').read(cr, uid, move, ['debit','credit','amount_currency','currency_id'])
                if move_read['debit']!=0.00: 
                    if move_read['currency_id'][0]==reval['comp_curr'][0]:
                        balbegcomp +=move_read['amount_currency']
                    elif move_read['currency_id'][0]==reval['second_curr'][0]:
                        balbegsec +=move_read['amount_currency']
                elif move_read['credit']!=0.00:
                    if move_read['currency_id'][0]==reval['comp_curr'][0]:
                        balbegcomp -=move_read['amount_currency']
                    elif move_read['currency_id'][0]==reval['secon_curr'][0]:
                        balbegsec -=move_read['amount_currency']
            ap_moves = self.pool.get('account.move.line').search(cr,uid, [('date','>=',period_read['date_start']),
                                                                          ('date','<=',period_read['date_stop']),
                                                                       ('account_id.include_pool','=',True),
                                                                       ])
            for ap_move in ap_moves:
                ap_move_read = self.pool.get('account.move.line').read(cr, uid, ap_move, ['debit','credit','amount_currency','currency_id'])
                if ap_move_read['debit']!=0.00: 
                    if ap_move_read['currency_id'][0]==reval['comp_curr'][0]:
                        balapcomp +=ap_move_read['amount_currency']
                    elif ap_move_read['currency_id'][0]==reval['second_curr'][0]:
                        balapsec +=ap_move_read['amount_currency']
                elif ap_move_read['credit']!=0.00:
                    if ap_move_read['currency_id'][0]==reval['comp_curr'][0]:
                        balapcomp -=ap_move_read['amount_currency']
                    elif ap_move_read['currency_id'][0]==reval['second_curr'][0]:
                        balapsec -=ap_move_read['amount_currency']
            balbegcomp #1
            log2 = log2+'\n'+ 'Beginning Pool Equivalent(Company Currency): '+str(balbegcomp)
            print log2
            balapcomp #2  
            log2 = log2+'\n'+ 'After Posting Pool Equivalent(Company Currency): '+str(balapcomp)
            print log2
            balbegsec = balbegsec/reval['start_rate'] #3
            log2 = log2+'\n'+ str(balbegsec)
            print log2
            balapsec = balapsec/reval['post_rate'] #4
            log2 = log2+'\n'+ str(balapsec)
            print log2
            pt_beg = balbegcomp + balbegsec #5
            log2 = log2+'\n'+ str(pt_beg)
            print log2
            pt_ap = balapsec+balapcomp #6
            log2 = log2+'\n'+ str(pt_ap)
            print log2
            pf_beg_comp = balbegcomp / pt_beg #7
            log2 = log2+'\n'+ str(pf_beg_comp)
            print log2
            pf_ap_comp = balapcomp / pt_ap #8
            log2 = log2+'\n'+ str(pf_ap_comp)
            print log2
            pf_beg_sec = balbegsec / pt_beg #9
            log2 = log2+'\n'+ str(pf_beg_sec)
            print log2
            pf_ap_sec= balapsec / pt_ap #10
            log2 = log2+'\n'+ str(pf_ap_sec)
            print log2
            rcf_beg = (reval['post_rate']/reval['start_rate']) - 1 #11
            log2 = log2+'\n'+ str(rcf_beg)
            print log2
            rcf_ap =(reval['end_rate']/reval['post_rate']) - 1 #12
            log2 = log2+'\n'+ str(rcf_ap)
            print log2
            rf_beg = (pf_beg_sec * rcf_beg) #13
            log2 = log2+'\n'+ str(rf_beg)
            print log2
            rf_ap = (pf_ap_sec * rcf_ap) #14
            log2 = log2+'\n'+ str(rf_ap)
            print log2
            log2 = reval['reval_log']+log2
            vals = {'pool_equivalent_beg_comp':balbegcomp,'pool_equivalent_beg_second':balbegsec,
                'pool_equivalent_ap_comp':balapcomp,'pool_equivalent_ap_second':balapsec,'pool_total_beg':pt_beg,
                'pool_total_ap':pt_ap,'portion_factor_beg_comp':pf_beg_comp,'portion_factor_beg_second':pf_beg_sec,
                'portion_factor_ap_comp':pf_ap_comp,'portion_factor_ap_second':pf_ap_sec,'rate_change_beg_second':rcf_beg,
                'rate_change_ap_second':rcf_ap,'reval_beg':rf_beg, 'reval_ap':rf_ap,'state':'revaluated', 'reval_log':log2,
                }
            self.write(cr, uid, ids, vals)
            self.pool_account(cr, uid, ids)
        return self.revaluate(cr, uid, ids)
    
    def revaluate(self, cr, uid, ids, context=None):
        for reval in self.read(cr, uid, ids, context=None):
            num_13 = reval['reval_beg']
            num_14 = reval['reval_ap']
            php_beg = reval['pool_equivalent_beg_comp']
            usd_beg = reval['pool_equivalent_beg_second']
            php_ap = reval['pool_equivalent_beg_comp']
            usd_ap = reval['pool_equivalent_beg_second']
            for reval_acc in reval['income_ids']:
                reval_acc_read = self.pool.get('account.revaluation.account').read(cr, uid, reval_acc,context=None)
                beg_bal = reval_acc_read['comp_bal_beg']
                post_bal = reval_acc_read['bal_ap']
                diff = (beg_bal * num_13) + ((post_bal + (beg_bal * num_13))*num_14)
                ending_bal = post_bal + diff
                gain_loss = ending_bal - post_bal
                self.pool.get('account.revaluation.account').write(cr, uid, reval_acc,{'diff':diff,'bal_end':ending_bal,'gain_loss_amt':gain_loss})
            for reval_acc in reval['expense_ids']:
                reval_acc_read = self.pool.get('account.revaluation.account').read(cr, uid, reval_acc,context=None)
                beg_bal = reval_acc_read['comp_bal_beg']
                post_bal = reval_acc_read['bal_ap']
                diff = (beg_bal * num_13) + ((post_bal + (beg_bal * num_13))*num_14)
                ending_bal = post_bal + diff
                gain_loss = ending_bal - post_bal
                self.pool.get('account.revaluation.account').write(cr, uid, reval_acc,{'diff':diff,'bal_end':ending_bal,'gain_loss_amt':gain_loss})
            for reval_acc in reval['equity_ids']:
                reval_acc_read = self.pool.get('account.revaluation.account').read(cr, uid, reval_acc,context=None)
                beg_bal = reval_acc_read['comp_bal_beg']
                post_bal = reval_acc_read['bal_ap']
                diff = (beg_bal * num_13) + ((post_bal + (beg_bal * num_13))*num_14)
                ending_bal = post_bal + diff
                gain_loss = ending_bal - post_bal
                self.pool.get('account.revaluation.account').write(cr, uid, reval_acc,{'diff':diff,'bal_end':ending_bal,'gain_loss_amt':gain_loss})
            for reval_acc in reval['pat_ids']:
                reval_acc_read = self.pool.get('account.revaluation.account').read(cr, uid, reval_acc,context=None)
                beg_bal = reval_acc_read['comp_bal_beg']
                post_bal = reval_acc_read['bal_ap']
                diff = (beg_bal * num_13) + ((post_bal + (beg_bal * num_13))*num_14)
                ending_bal = post_bal + diff
                gain_loss = ending_bal - post_bal
                self.pool.get('account.revaluation.account').write(cr, uid, reval_acc,{'diff':diff,'bal_end':ending_bal,'gain_loss_amt':gain_loss})
        return self.revaluate_pool(cr, uid, ids)
    
    def revaluate_pool(self, cr, uid, ids, context=None):
        for reval in self.read(cr, uid, ids, context=None):
            num_13 = reval['reval_beg']
            num_14 = reval['reval_ap']
            php_beg = reval['pool_equivalent_beg_comp']
            usd_beg = reval['pool_equivalent_beg_second']
            php_ap = reval['pool_equivalent_beg_comp']
            usd_ap = reval['pool_equivalent_beg_second']
            for reval_acc in reval['pool_account_ids']:
                reval_acc_read = self.pool.get('account.revaluation.pool.account').read(cr, uid, reval_acc,context=None)
                beg_bal = reval_acc_read['comp_bal_beg']
                post_bal = reval_acc_read['bal_ap']
                diff = (beg_bal * num_13) + ((post_bal + (beg_bal * num_13))*num_14)
                ending_bal = post_bal + diff
                gain_loss = ending_bal - post_bal
                self.pool.get('account.revaluation.pool.account').write(cr, uid, reval_acc,{'diff':diff,'bal_end':ending_bal})
        return True
#        return self.revaluate_equity(cr, uid, ids)
    
#    def revaluate_equity(self, cr, uid, ids, context=None):
#        for reval in self.read(cr, uid, ids, context=None):
#            num_13 = reval['reval_beg']
#            num_14 = reval['reval_ap']
#            php_beg = reval['pool_equivalent_beg_comp']
#            usd_beg = reval['pool_equivalent_beg_second']
#            php_ap = reval['pool_equivalent_beg_comp']
#            usd_ap = reval['pool_equivalent_beg_second']
#            for reval_acc in reval['equity_account_ids']:
#                reval_acc_read = self.pool.get('account.revaluation.equity.account').read(cr, uid, reval_acc,context=None)
#                beg_bal = reval_acc_read['comp_bal_beg']
#                post_bal = reval_acc_read['bal_ap']
#                diff = (beg_bal * num_13) + ((post_bal + (beg_bal * num_13))*num_14)
#                ending_bal = post_bal + diff
#                gain_loss = ending_bal - post_bal
#                self.pool.get('account.revaluation.equity.account').write(cr, uid, reval_acc,{'diff':diff,'bal_end':ending_bal})
#        return True
    
    def pool_account(self, cr, uid, ids, context=None):
        for reval in self.read(cr, uid, ids, context=None):
            acc_search = self.pool.get('account.account').search(cr, uid, [('include_pool','=',True)])
            period_read = self.pool.get('account.period').read(cr, uid, reval['period_id'][0],context=None)
            pool_acc_search = self.pool.get('account.revaluation.pool.account').search(cr, uid,[('period_close_id','=',reval['id'])])
            self.pool.get('account.revaluation.pool.account').unlink(cr, uid,pool_acc_search)
            for acc in acc_search:
                acc_read = self.pool.get('account.account').read(cr, uid, acc,context=None)
                vals = {
                'account_id':acc,
                'period_close_id':reval['id'],
                }
                moves = self.pool.get('account.move.line').search(cr, uid, [('account_id','=',acc),('date','<',period_read['date_start'])])
                comp_bal_beg = False
                balbeg = False
                sec_bal_beg = False
                comp_bal_ap = False
                balap = False
                sec_bal_ap = False
                currency = False
                for move in moves:
                    move_read = self.pool.get('account.move.line').read(cr, uid, move, ['debit','credit','amount_currency','currency_id'])
                    if move_read['currency_id'][0]==reval['comp_curr'][0]:
                        comp_bal_beg += move_read['debit']-move_read['credit']
                    elif move_read['currency_id'][0]==reval['second_curr'][0]:
                        if move_read['debit']==0.00:
                            sec_bal_beg -=move_read['amount_currency'] / reval['start_rate']
                        elif move_read['credit']==0.00:
                            sec_bal_beg +=move_read['amount_currency'] / reval['start_rate']
                moves = self.pool.get('account.move.line').search(cr, uid, [('account_id','=',acc),
                                                                            ('date','>=',period_read['date_start']),
                                                                            ('date','<=',period_read['date_stop'])])
                for move in moves:
                    move_read = self.pool.get('account.move.line').read(cr, uid, move, ['debit','credit','amount_currency','currency_id'])
                    if move_read['currency_id'][0]==reval['comp_curr'][0]:
                        comp_bal_ap += move_read['debit']-move_read['credit']
                    elif move_read['currency_id'][0]==reval['second_curr'][0]:
                        if move_read['debit']==0.00:
                            sec_bal_ap-=move_read['amount_currency'] / reval['post_rate']
                        elif move_read['credit']==0.00:
                            sec_bal_ap+=move_read['amount_currency'] / reval['post_rate']
                if acc_read['currency_id']:
                    currency = acc_read['currency_id'][0]
                    balbeg = sec_bal_beg
                    balap = balbeg + sec_bal_ap
                elif not acc_read['currency_id']:
                    currency = acc_read['company_currency_id'][0]
                    balbeg = comp_bal_beg
                    balap = balbeg + comp_bal_ap
                
                vals.update({'comp_bal_beg':balbeg,'currency_id':currency,'bal_ap':balap})
                self.pool.get('account.revaluation.pool.account').create(cr, uid, vals)
        return True
    
    def checkRate(self, cr, uid, ids, context=None):
        for reval in self.read(cr, uid, ids, context=None):
            rates = self.pool.get('res.currency.rate').search(cr, uid, [('currency_id','=',reval['second_curr'][0])], limit=1, order='name desc')
            rateRead = self.pool.get('res.currency.rate').read(cr, uid, rates[0], context=None)
            updateRate = {
                    'end_rate':reval['end_rate'],
                    'post_rate':reval['post_rate'],
                    'weighted_rate':reval['weighted_rate'],
                    }
            self.pool.get('res.currency.rate').write(cr, uid, rates[0],updateRate)
            period = reval['period_id'][0]
            period = period + 1
            periodREad = self.pool.get('account.period').read(cr, uid, period, ['date_start'])
            newRate = {
                    'rate':reval['end_rate'],
                    'name':periodREad['date_start'],
                    'currency_id':reval['second_curr'][0],
                    }
            self.pool.get('res.currency.rate').create(cr, uid, newRate)
        return True
    
    def post_equityEntries(self, cr, uid, ids, context=None):
        for reval in self.read(cr, uid, ids, context=None):
            journal_id = reval['journal_id'][0]
            move = {
                'period_id':reval['period_id'][0],
                'date':reval['name'],
                'journal_id':journal_id,
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            for reval_acc in reval['equity_ids']:
                acc_read = self.pool.get('account.revaluation.account').read(cr, uid, reval_acc,context=None)
                analytic_read = self.pool.get('account.analytic.account').read(cr, uid, acc_read['analytic_id'][0],['name','ntm_type', 'region_id','normal_account'])
                regionRead = self.pool.get('region.config').read(cr, uid, analytic_read['region_id'][0], ['gain_loss_acct'])
                glAcc = regionRead['gain_loss_acct'][0]
                glRead = self.pool.get('account.analytic.account').read(cr, uid, glAcc, ['normal_account'])
                if acc_read['diff']>0.00:
                    credit = 0.00
                    debit = acc_read['diff']
                    debit2 = 0.00
                    credit2 = acc_read['diff']
                    name = 'Loss of ' + analytic_read['name']
                elif acc_read['diff']<0.00:
                    debit = 0.00
                    credit = acc_read['diff']
                    credit = credit * -1
                    credit2 = 0.00
                    debit2 = acc_read['diff']
                    debit2 = debit2 * -1
                    name = 'Gain of ' + analytic_read['name']
                move_line = {
                            'name':name,
                            'journal_id':journal_id,
                            'period_id':reval['period_id'][0],
                            'account_id':acc_read['account_id'][0],
                            'debit':debit,
                            'credit':credit,
                            'date':reval['name'],
                            'move_id':move_id,
                            'analytic_account_id':acc_read['analytic_id'][0],
                            'amount_currency':acc_read['diff'],
                            'currency_id':reval['comp_curr'][0],
                        }
                self.pool.get('account.move.line').create(cr, uid, move_line)
                move_line = {
                        'name':name,
                        'journal_id':journal_id,
                        'period_id':reval['period_id'][0],
                        'account_id':glRead['normal_account'][0],
                        'debit':debit2,
                        'credit':credit2,
                        'date':reval['name'],
                        'move_id':move_id,
                        'analytic_account_id':glAcc,
                        'amount_currency':acc_read['diff'],
                        'currency_id':reval['comp_curr'][0],
                    }
                self.pool.get('account.move.line').create(cr, uid, move_line)
            self.write(cr, uid, ids, {'equity_move_id':move_id})
            self.pool.get('account.move').post(cr, uid, [move_id])
        return True
    
    def post_incomeEntries(self, cr, uid, ids, context=None):
        for reval in self.read(cr, uid, ids, context=None):
            journal_id = reval['journal_id'][0]
            move = {
                'period_id':reval['period_id'][0],
                'date':reval['name'],
                'journal_id':journal_id,
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            ctr = False
            for reval_acc in reval['income_ids']:
                ctr +=1
                acc_read = self.pool.get('account.revaluation.account').read(cr, uid, reval_acc,context=None)
                analytic_read = self.pool.get('account.analytic.account').read(cr, uid, acc_read['analytic_id'][0],['name','ntm_type', 'region_id','normal_account'])
                regionRead = self.pool.get('region.config').read(cr, uid, analytic_read['region_id'][0], ['gain_loss_acct'])
                glAcc = regionRead['gain_loss_acct'][0]
                glRead = self.pool.get('account.analytic.account').read(cr, uid, glAcc, ['normal_account'])
                test = str(ctr) + '. ' + analytic_read['name']
                if acc_read['diff']>0.00:
                    credit = 0.00
                    debit = acc_read['diff']
                    debit2 = 0.00
                    credit2 = acc_read['diff']
                    name = 'Loss of ' + analytic_read['name']
                elif acc_read['diff']<0.00:
                    debit = 0.00
                    credit = acc_read['diff']
                    credit = credit * -1
                    credit2 = 0.00
                    debit2 = acc_read['diff']
                    debit2 = debit2 * -1
                    name = 'Gain of ' + analytic_read['name']
                if acc_read['diff']!=0.00:
                    move_line = {
                                'name':name,
                                'journal_id':journal_id,
                                'period_id':reval['period_id'][0],
                                'account_id':acc_read['account_id'][0],
                                'debit':debit,
                                'credit':credit,
                                'date':reval['name'],
                                'move_id':move_id,
                                'analytic_account_id':acc_read['analytic_id'][0],
                                'amount_currency':acc_read['diff'],
                                'currency_id':reval['comp_curr'][0],
                            }
                    self.pool.get('account.move.line').create(cr, uid, move_line)
                    move_line = {
                            'name':name,
                            'journal_id':journal_id,
                            'period_id':reval['period_id'][0],
                            'account_id':glRead['normal_account'][0],
                            'debit':debit2,
                            'credit':credit2,
                            'date':reval['name'],
                            'move_id':move_id,
                            'analytic_account_id':glAcc,
                            'amount_currency':acc_read['diff'],
                            'currency_id':reval['comp_curr'][0],
                        }
                    self.pool.get('account.move.line').create(cr, uid, move_line)
            self.write(cr, uid, ids, {'income_move_id':move_id})
            self.pool.get('account.move').post(cr, uid, [move_id])
        return True
    
    def post_expenseEntries(self, cr, uid, ids, context=None):
        for reval in self.read(cr, uid, ids, context=None):
            journal_id = reval['journal_id'][0]
            move = {
                'period_id':reval['period_id'][0],
                'date':reval['name'],
                'journal_id':journal_id,
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            for reval_acc in reval['expense_ids']:
                acc_read = self.pool.get('account.revaluation.account').read(cr, uid, reval_acc,context=None)
                analytic_read = self.pool.get('account.analytic.account').read(cr, uid, acc_read['analytic_id'][0],['name','ntm_type', 'region_id','normal_account'])
                regionRead = self.pool.get('region.config').read(cr, uid, analytic_read['region_id'][0], ['gain_loss_acct'])
                glAcc = regionRead['gain_loss_acct'][0]
                glRead = self.pool.get('account.analytic.account').read(cr, uid, glAcc, ['normal_account'])
                if acc_read['diff']>0.00:
                    credit = 0.00
                    debit = acc_read['diff']
                    debit2 = 0.00
                    credit2 = acc_read['diff']
                    name = 'Loss of ' + analytic_read['name']
                elif acc_read['diff']<0.00:
                    debit = 0.00
                    credit = acc_read['diff']
                    credit = credit * -1
                    credit2 = 0.00
                    debit2 = acc_read['diff']
                    debit2 = debit2 * -1
                    name = 'Gain of ' + analytic_read['name']
                move_line = {
                            'name':name,
                            'journal_id':journal_id,
                            'period_id':reval['period_id'][0],
                            'account_id':acc_read['account_id'][0],
                            'debit':debit,
                            'credit':credit,
                            'date':reval['name'],
                            'move_id':move_id,
                            'analytic_account_id':acc_read['analytic_id'][0],
                            'amount_currency':acc_read['diff'],
                            'currency_id':reval['comp_curr'][0],
                        }
                self.pool.get('account.move.line').create(cr, uid, move_line)
                move_line = {
                        'name':name,
                        'journal_id':journal_id,
                        'period_id':reval['period_id'][0],
                        'account_id':glRead['normal_account'][0],
                        'debit':debit2,
                        'credit':credit2,
                        'date':reval['name'],
                        'move_id':move_id,
                        'analytic_account_id':glAcc,
                        'amount_currency':acc_read['diff'],
                        'currency_id':reval['comp_curr'][0],
                    }
                self.pool.get('account.move.line').create(cr, uid, move_line)
            self.write(cr, uid, ids, {'expense_move_id':move_id})
            self.pool.get('account.move').post(cr, uid, [move_id])
        return True
    def post_patEntries(self, cr, uid, ids, context=None):
        for reval in self.read(cr, uid, ids, context=None):
            journal_id = reval['journal_id'][0]
            move = {
                'period_id':reval['period_id'][0],
                'date':reval['name'],
                'journal_id':journal_id,
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            ctr = False
            for reval_acc in reval['pat_ids']:
                ctr+=1
                acc_read = self.pool.get('account.revaluation.account').read(cr, uid, reval_acc,context=None)
                analytic_read = self.pool.get('account.analytic.account').read(cr, uid, acc_read['analytic_id'][0],['name','ntm_type', 'region_id','normal_account'])
                accountRead = self.pool.get('account.account').read(cr, uid, analytic_read['normal_account'][0], ['gain_loss'])
                glAcc = accountRead['gain_loss'][0]
                glRead = self.pool.get('account.analytic.account').read(cr, uid, glAcc, ['normal_account'])
                name = False
                debit = False
                debit2 = False
                credit = False
                credit2 = False
                if acc_read['diff']==0.00:
                    credit = 0.00
                    debit = 0.00
                    debit2 = 0.00
                    credit2 = 0.00
                    name = 'No gain or loss for ' + analytic_read['name']
                elif acc_read['diff']>0.00:
                    credit = 0.00
                    debit = acc_read['diff']
                    debit2 = 0.00
                    credit2 = acc_read['diff']
                    name = 'Loss of ' + analytic_read['name']
                elif acc_read['diff']<0.00:
                    debit = 0.00
                    credit = acc_read['diff']
                    credit = credit * -1
                    credit2 = 0.00
                    debit2 = acc_read['diff']
                    debit2 = debit2 * -1
                    name = 'Gain of ' + analytic_read['name']
                move_line = {
                            'name':name,
                            'journal_id':journal_id,
                            'period_id':reval['period_id'][0],
                            'account_id':acc_read['account_id'][0],
                            'debit':debit,
                            'credit':credit,
                            'date':reval['name'],
                            'move_id':move_id,
                            'analytic_account_id':acc_read['analytic_id'][0],
                            'amount_currency':acc_read['diff'],
                            'currency_id':reval['comp_curr'][0],
                        }
                self.pool.get('account.move.line').create(cr, uid, move_line)
                move_line = {
                        'name':name,
                        'journal_id':journal_id,
                        'period_id':reval['period_id'][0],
                        'account_id':glRead['normal_account'][0],
                        'debit':debit2,
                        'credit':credit2,
                        'date':reval['name'],
                        'move_id':move_id,
                        'analytic_account_id':glAcc,
                        'amount_currency':acc_read['diff'],
                        'currency_id':reval['comp_curr'][0],
                    }
                self.pool.get('account.move.line').create(cr, uid, move_line)
            self.write(cr, uid, ids, {'pat_move_id':move_id})
            self.pool.get('account.move').post(cr, uid, [move_id])
        return True
    
    def post_entries(self, cr, uid, ids, context=None):
        for reval in self.read(cr, uid, ids, context=None):
            journal_id = reval['journal_id'][0]
            move = {
                'period_id':reval['period_id'][0],
                'date':reval['name'],
                'journal_id':journal_id,
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            ctr = False
            for reval_acc in reval['account_ids']:
                acc_read = self.pool.get('account.revaluation.account').read(cr, uid, reval_acc,context=None)
                ctr +=1
                analytic_read = self.pool.get('account.analytic.account').read(cr, uid, acc_read['analytic_id'][0],['name','ntm_type', 'region_id','normal_account'])
                glAcc = False
                if analytic_read['ntm_type'] in ['income','expense','equity']:
                    regionRead = self.pool.get('region.config').read(cr, uid, analytic_read['region_id'][0], ['gain_loss_acct'])
                    glAcc = regionRead['gain_loss_acct'][0]
                elif analytic_read['ntm_type'] not in ['income','expense','equity']:
                    aaRead = self.pool.get('account.account').read(cr, uid, analytic_read['normal_account'][0],['gain_loss'])
                    glAcc = aaRead['gain_loss'][0]
                credit = 0.00
                debit = 0.00
                credit2 = 0.00
                debit2 = 0.00
                if acc_read['diff']>0.00:
                    credit = 0.00
                    debit = acc_read['diff']
                    name = 'Loss of ' + analytic_read['name']
                elif acc_read['diff']<0.00:
                    debit = 0.00
                    credit = acc_read['diff']
                    credit = credit * -1
                    name = 'Gain of ' + analytic_read['name']
                move_line = {
                            'name':name,
                            'journal_id':journal_id,
                            'period_id':reval['period_id'][0],
                            'account_id':acc_read['account_id'][0],
                            'debit':debit,
                            'credit':credit,
                            'date':reval['name'],
                            'move_id':move_id,
                            'analytic_account_id':acc_read['analytic_id'][0],
                            'amount_currency':acc_read['diff'],
                            'currency_id':reval['comp_curr'][0],
                        }
                self.pool.get('account.move.line').create(cr, uid, move_line)
                if acc_read['diff']>0.00:
                    debit2 = 0.00
                    credit2 = acc_read['diff']
                    name = 'Loss of ' + analytic_read['name']
                elif acc_read['diff']<0.00:
                    credit2 = 0.00
                    debit2 = acc_read['diff']
                    debit2 = debit2 * -1
                    name = 'Gain of ' + analytic_read['name']
                move_line = {
                        'name':name,
                        'journal_id':journal_id,
                        'period_id':reval['period_id'][0],
                        'account_id':acc_read['account_id'][0],
                        'debit':debit2,
                        'credit':credit2,
                        'date':reval['name'],
                        'move_id':move_id,
                        'analytic_account_id':glAcc,
                        'amount_currency':acc_read['diff'],
                        'currency_id':reval['comp_curr'][0],
                    }
                self.pool.get('account.move.line').create(cr, uid, move_line)
            self.write(cr, uid, ids, {'move_id':move_id,'state':'verified'})
            #self.pool.get('account.move').post(cr, uid, [move_id])
            self.checkRate(cr, uid, ids)
        return True
    
    def verify(self, cr, uid, ids, context=None):
        self.checkRate(cr, uid, ids)
        return self.write(cr, uid, ids, {'state':'verified'})
                
account_revaluation()

class account_revaluation_accounts(osv.osv):
    _name = 'account.revaluation.account'
    _columns = {
        'account_id':fields.many2one('account.account','Account'),
        'gainloss_account_id':fields.many2one('account.analytic.account','Gain Loss Account'),
        'analytic_id':fields.many2one('account.analytic.account','Analytic Account'),
        'comp_bal_beg':fields.float('Beginning Balance',digits_compute=dp.get_precision('Account')),
        'adjustment':fields.float('Exchange Rate Adjustment',digits_compute=dp.get_precision('Account'),help="Exchange Rate Adjustment"),
        'bal_ap':fields.float('Balance after Posting',digits_compute=dp.get_precision('Account')),
        'diff':fields.float('Diff'),
        'ntm_type':fields.selection([('income','Income'),
                                         ('expense','Expense'),
                                         ('gl','Gain Loss'),
                                         ('pat','PAT Account'),
                                         ('project','Project Account'),
                                         ('equity','Equity')],'Account Type'),
        'period_close_id':fields.many2one('account.revaluation',ondelete='cascade'),
        'gain_loss_amt':fields.float('Gain/Loss Amount'),
        'bal_end':fields.float('Ending Balance', digits_compute=dp.get_precision('Account')),
        }
    _order = "bal_end asc"
account_revaluation_accounts()

class account_revaluation_pool_account(osv.osv):
    _name = 'account.revaluation.pool.account'
    _columns = {
        'account_id':fields.many2one('account.account','Account'),
        'currency_id':fields.many2one('res.currency','Currency'),
        'comp_bal_beg':fields.float('Beginning Balance',digits_compute=dp.get_precision('Account')),
        'bal_ap':fields.float('Balance after Posting',digits_compute=dp.get_precision('Account')),
        'diff':fields.float('Diff'),
        'period_close_id':fields.many2one('account.revaluation',ondelete='cascade'),
        'gain_loss_amt':fields.float('Gain/Loss Amount'),
        'bal_end':fields.float('Ending Balance', digits_compute=dp.get_precision('Account')),
        }
account_revaluation_pool_account()

class ar2(osv.osv):
    
    _inherit='account.revaluation'
    _columns = {
        'income_ids':fields.one2many('account.revaluation.account','period_close_id','Accounts for Revaluation', domain=[('ntm_type','=','income')]),
        'expense_ids':fields.one2many('account.revaluation.account','period_close_id','Accounts for Revaluation',domain=[('ntm_type','=','expense')]),
        'equity_ids':fields.one2many('account.revaluation.account','period_close_id','Accounts for Revaluation',domain=[('ntm_type','=','equity')]),
        'pat_ids':fields.one2many('account.revaluation.account','period_close_id','Accounts for Revaluation',domain=[('ntm_type','=','pat')]),
        'project_ids':fields.one2many('account.revaluation.account','period_close_id','Accounts for Revaluation',domain=[('ntm_type','=','project')]),
        'pool_account_ids':fields.one2many('account.revaluation.pool.account','period_close_id','Pool Accounts'),
        'income_move_id':fields.many2one('account.move','Journal Entry'),
        'income_move_ids': fields.related('income_move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'expense_move_id':fields.many2one('account.move','Journal Entry'),
        'expense_move_ids': fields.related('expense_move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'pat_move_id':fields.many2one('account.move','Journal Entry'),
        'pat_move_ids': fields.related('pat_move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'project_move_id':fields.many2one('account.move','Journal Entry'),
        'project_move_ids': fields.related('expense_move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'equity_move_id':fields.many2one('account.move','Journal Entry'),
        'equity_move_ids': fields.related('equity_move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),        
        }
ar2()

class account_period(osv.osv):
    _inherit = 'account.period'
    
    def revaluate_period(self, cr, uid, ids, context=None):
        for period in self.read(cr, uid, ids, context=None):
            period_id = period['id']
            checkReval=self.pool.get('account.revaluation').search(cr, uid, [('period_id','=',period_id)])
            if not checkReval:
                return {
                    'name': 'Revaluate',
                    'view_type':'form',
                    'nodestroy': True,
                    'target': 'new',
                    'view_mode':'form',
                    'res_model':'account.revaluation',
                    'type':'ir.actions.act_window',
                    'context':{'default_period_id':period_id},}
            elif checkReval:
                raise osv.except_osv(_('Warning!'), _('There is an existing revaluation document for this period!'))
account_period()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: