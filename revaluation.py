import time
import datetime
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
from stringprep import b1_set

class new_reval(osv.osv):
		
	_name = 'new.reval'
	_description = "New Revaluation Table"
	def _compute_sre_amount(self, cr, uid, ids, field, arg, context=None):
		rec = self.browse(cr, uid, ids, context=None)
		result = {}
		for r in rec:
			amount = r.rate_sr
			result[r.id]=1/amount
		return result
	def _compute_pre_amount(self, cr, uid, ids, field, arg, context=None):
		rec = self.browse(cr, uid, ids, context=None)
		result = {}
		for r in rec:
			amount = r.rate_pr
			result[r.id] = 1/amount
		return result
	def _compute_ere_amount(self, cr, uid, ids, field, arg, context=None):
		rec = self.browse(cr, uid, ids, context=None)
		result = {}
		for r in rec:
			amount = r.rate_er
			result[r.id] = 1/amount
		return result
	def _rcf1_amount(self, cr, uid, ids, field,arg, context=None):
		rec = self.browse(cr, uid, ids, context=None)
		result = {}
		for r in rec:
			amount = r.rate_sre / r.rate_pre
			result[r.id] = amount - 1
		return result
		
	def _rcf2_amount(self, cr, uid, ids, field,arg, context=None):
		rec = self.browse(cr, uid, ids, context=None)
		result = {}
		for r in rec:
			amount = r.rate_pre / r.rate_ere
			result[r.id] = amount - 1
		return result
	def _get_journal(self, cr, uid, context=None):
		if context is None:
			context = {}
		res = self.pool.get('account.journal').search(cr, uid, [('type','=','arj')],limit=1)
		return res and res[0] or False
	def _getSR(self, cr, uid, ids, context=None):
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
			curr = False
		rate_search = self.pool.get('res.currency.rate').search(cr, uid, [('currency_id','=',curr),('name','>=',period_read['date_start']),('name','<=',period_read['date_stop'])])
		if rate_search:
			rate_read = self.pool.get('res.currency.rate').read(cr, uid, rate_search[0],['rate'])
			return rate_read['rate']
		
	_columns = {
		'name':fields.char('Revaluation ID', size=64),
		'period_id':fields.many2one('account.period', 'Revaluated Period'),
		'src_exchange_ids':fields.many2many('forex.transaction','reval_exc_src_rel','forex_id','reval_id','Exchanges'),
        'dest_exchange_ids':fields.many2many('forex.transaction','reval_exc_dest_rel','forex_id','reval_id','Exchanges'),
		'rate_sr':fields.float('Start Rate'),
		'rate_pr':fields.float('Post Rate'),
		'journal_id':fields.many2one('account.journal','Journal',),
		'rate_er':fields.float('End Rate'),
		'rate_sre':fields.function(_compute_sre_amount, method=True, type='float', string='Start Rate', store=False,digits=(16,8)),
		'rate_pre':fields.function(_compute_pre_amount, method=True, type='float', string='Post Rate', store=False,digits=(16,8)),
		'rate_ere':fields.function(_compute_ere_amount, method=True, type='float', string='End Rate', store=False,digits=(16,8)),
		'primary_curr':fields.many2one('res.currency','Currency'),
		#'pri_curr':fields.function(_pri_curr, method=False, type='many2one', relation='res.currency',string='Primary Currency', store=True),
		'secondary_curr':fields.many2one('res.currency','Currency'),
		'pri_pool':fields.float('Money Pool'),
		'sec_pool':fields.float('Money Pool'),
		'pri_appool':fields.float('Money Pool'),
		'date':fields.date('Revaluation Date'),
		'sec_appool':fields.float('Money Pool'),
		'state':fields.selection([
							('draft','Draft'),
							('fetched','Accounts Fetched'),
							('revaluated','Revaluated'),
							('entryGenerated','Entries Generated'),
							('updateSOA','SOAs Updated and Sent'),
						],'State'),
		'pool_total':fields.float('Total Money Pool'),
		'pool_aptotal':fields.float('Total Money Pool(After Posting)'),
		'pri_pf':fields.float('Portion Factor',digits=(16,8)),
		'sec_pf':fields.float('Portion Factor',digits=(16,8)),
		'pri_appf':fields.float('Portion Factor',digits=(16,8)),
		'sec_appf':fields.float('Portion Factor',digits=(16,8)),
		'rcf1':fields.function(_rcf1_amount, method=True, type='float', string='Rate Change Factor 1', store=False,digits=(16,8)),
		'rcf2':fields.function(_rcf2_amount, method=True, type='float', string='Rate Change Factor 2', store=False,digits=(16,8)),
		'ugl_fgl_move_id':fields.many2one('account.move','Journal Entry'),
        'ugl_fgl_move_ids': fields.related('ugl_fgl_move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
		'region_fgl_move_id':fields.many2one('account.move','Journal Entry'),
        'region_fgl_move_ids': fields.related('region_fgl_move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
		'nonregion_fgl_move_id':fields.many2one('account.move','Journal Entry'),
        'nonregion_fgl_move_ids': fields.related('nonregion_fgl_move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
		}
	def _get_ex_src(self, cr, uid, ids, context=None):
		period_id = ids['default_period_id']
		period_read = self.pool.get('account.period').read(cr, uid, ids['default_period_id'],['company_id'])
		comp_read = self.pool.get('res.company').read(cr, uid, period_read['company_id'][0],['currency_id'])
		currency = comp_read['currency_id'][0]
		srces = []
		srces = self.pool.get('forex.transaction').search(cr, uid, [('period_id','=',period_id),('src.currency_id','=',currency)])
		return srces
	
	def _getName(self, cr, uid, ids, context=None):
		period_id = ids['default_period_id']
		period_read = self.pool.get('account.period').read(cr, uid, ids['default_period_id'], ['name'])
		name = 'Revaluation for ' + period_read['name']
		return name
	def _get_ex_dest(self, cr, uid, ids, context=None):
		period_id = ids['default_period_id']
		period_read = self.pool.get('account.period').read(cr, uid, ids['default_period_id'],['company_id'])
		comp_read = self.pool.get('res.company').read(cr, uid, period_read['company_id'][0],['currency_id'])
		currency = comp_read['currency_id'][0]
		srces = []
		srces = self.pool.get('forex.transaction').search(cr, uid, [('period_id','=',period_id),('dest.currency_id','=',currency)])
		return srces
	def _get_pri_curr(self, cr, uid, ids, context=None):
		userRead = self.pool.get('res.users').read(cr, uid, uid, ['company_id'])
		compRead = self.pool.get('res.company').read(cr, uid, userRead['company_id'][0], ['currency_id'])
		return compRead['currency_id'][0]
	
	def _get_sec_curr2(self, cr, uid, ids, context=None):
		userRead = self.pool.get('res.users').read(cr, uid, uid, ['company_id'])
		compRead = self.pool.get('res.company').read(cr, uid, userRead['company_id'][0], ['sec_currency'])
		return compRead['sec_currency'][0]
		
	def _get_sec_curr(self, cr, uid, ids, context=None):
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

	_defaults = {
		'journal_id':_get_journal,
		'name':_getName,
		'date':lambda *a: time.strftime('%Y-%m-%d'),
		'primary_curr':_get_pri_curr,
		'secondary_curr':_get_sec_curr2,
		'src_exchange_ids':_get_ex_src,
		'dest_exchange_ids':_get_ex_dest,
		'rate_sr':1.00,
		'rate_pr':1.00,
		'rate_er':1.00,
		}
new_reval()

class new_reval_accts(osv.osv):
	_name = 'new.reval.accts'
	_description = "Accounts"
	
	def _eba_amount(self, cr, uid, ids, field,arg, context=None):
		rec = self.browse(cr, uid, ids, context=None)
		result = {}
		for r in rec:
			rate_er = r.reval_id.rate_er
			if r.is_pr == True:
				result[r.id] = r.beg_bal_src+r.phpe_postings_sr+r.post_corr+r.diff_total_pr
			elif r.pri_pool == True:
				result[r.id] = r.beg_bal_src+r.phpe_postings_pr
			elif r.sec_pool == True:
				result[r.id] = (r.beg_bal_src + r.sec_postings)*rate_er
		return result
	
	_columns = {
		'account_id':fields.many2one('account.account','Normal Account'),
		'analytic_id':fields.many2one('account.analytic.account','Analytic Account'),
		'acc_name':fields.char('Account Name', size=64, readonly=True),
		'pri_pool':fields.boolean('Primary Pool'),
		'sec_pool':fields.boolean('Secondary Pool'),
		'currency_id':fields.many2one('res.currency','Currency'),
		'is_pr':fields.boolean('Partially Revaluated'),
		'reval_id':fields.many2one('new.reval','Revaluation',ondelete='cascade'),
		'pool_id':fields.many2one('new.reval','Revaluation',ondelete='cascade'),
		'beg_bal_src':fields.float('Beginning Balance (SRC)'),
		'beg_bal_phpe':fields.float('Primary Equivalent by OpenERP'),
		'beg_bal_sr':fields.float('Primary Equivalent (SR)'),
		'pri_postings':fields.float('Total Primary Postings'),
		'sec_postings':fields.float('Total Secondary Postings'),
		'phpe_postings_sr':fields.float('Primary Equivalent (SR)'),
		'phpe_postings_pr':fields.float('Primary Equivalent (PR)'),
		'diff_sr_pr':fields.float('Posting Difference (PR-SR)'),
		'rev_beg_bal':fields.float('Revaluated Beginning Balance'),
		'diff1':fields.float('Diff1'),
		'diff1_pool':fields.float('Diff1 Pool'),
		'bal_ap':fields.float('Balance after Posting'),
		'bal_ap_diff1':fields.float('Total AP Balance + Diff 1'),
		'bal_ap_pool':fields.float('AP Balance Pool'),
		'diff2':fields.float('Diff2'),
		'end_bal_pr':fields.float('Ending Balance (PR)'),
		'end_bal_pool':fields.float('Pool Ending Balance'),
		'post_corr':fields.float('Posting Corrections(SR,PR)'),
		'diff_total_pr':fields.float('Diff Total PR Accounts'),
		'diff_total_sec':fields.float('Diff Total Secondary Currency Accounts'),
		'eba':fields.float('Ending Balance A'),
		'ebb':fields.float('Ending Balance B'),
		'ebc':fields.float('Ending Balance C'),
		}
new_reval_accts()

class new_reval2(osv.osv):
	_inherit = 'new.reval'
	_columns = {
		'acc_ids':fields.one2many('new.reval.accts','reval_id','Accounts for Revaluation'),
		'pool_ids':fields.one2many('new.reval.accts','pool_id','Money Pool Accounts'),
		}
	
	def pesr(self, cr, uid, ids, context=None):
		for reval in self.read(cr, uid, ids, context=None):
			reval_id = reval['id']
			period_read = self.pool.get('account.period').read(cr, uid, reval['period_id'][0],['date_start','date_stop'])
			userRead = self.pool.get('res.users').read(cr, uid, uid, context=None)
			compRead = self.pool.get('res.company').read(cr, uid, userRead['company_id'][0], ['currency_id'])
			sr = reval['rate_sre']
			pr = reval['rate_pre']
			er = reval['rate_ere']
			rcf1 = reval['rcf1']
			pri_pool_amt = 0.00
			sec_pool_amt = 0.00
			pri_appool = 0.00
			sec_appool = 0.00
			for acct in reval['pool_ids']:
				pesr = 0.00
				pri_postings = 0.00
				sec_postings = 0.00
				acctRead =self.pool.get('new.reval.accts').read(cr, uid, acct, context=None)
				if acctRead['pri_pool']==True:
					pesr = acctRead['beg_bal_src']
					pri_pool_amt +=pesr
				elif acctRead['sec_pool']==True:
					pesr = acctRead['beg_bal_src'] / sr
					sec_pool_amt +=pesr
				checkEntries = self.pool.get('account.move.line').search(cr, uid, [('account_id','=',acctRead['account_id'][0]),('period_id','=',reval['period_id'][0])])
				for posting in checkEntries:
					postingReader = self.pool.get('account.move.line').read(cr, uid, posting, context=None)
					if acctRead['sec_pool']==True:
						if postingReader['debit']>0.00:
							sec_postings +=postingReader['amount_currency']
						if postingReader['credit']>0.00:
							sec_postings -=postingReader['amount_currency']
					elif acctRead['pri_pool']==True:
						if postingReader['debit']>0.00:
							pri_postings +=postingReader['amount_currency']
						if postingReader['credit']>0.00:
							pri_postings -=postingReader['amount_currency']
				phpe_postings_sr = pri_postings + (sec_postings / sr)
				phpe_postings_pr = pri_postings + (sec_postings / pr)
				diff_sr_pr = phpe_postings_pr - phpe_postings_sr
				rev_beg_bal = 0.00
				diff1_pool = 0.00
				bal_ap = pesr + phpe_postings_sr
				bal_ap_pool = 0.00
				end_bal_pool = 0.00
				diff_total_sec = 0.00
				if acctRead['pri_pool']==True:
					rev_beg_bal = pesr
					bal_ap_pool = acctRead['beg_bal_src'] + phpe_postings_pr
					pri_appool +=bal_ap_pool
					end_bal_pool = bal_ap_pool
				elif acctRead['sec_pool']==True:
					rev_beg_bal = pesr + (pesr*rcf1)
					diff1_pool = pesr * rcf1
					bal_ap_pool = (acctRead['beg_bal_src'] + sec_postings)/pr
					sec_appool += bal_ap_pool
					end_bal_pool = (acctRead['beg_bal_src'] + sec_postings)/er
					diff_total_sec = (acctRead['beg_bal_src'] + sec_postings)*((1/er)-(1/sr))
				acctVals = {
						'beg_bal_phpe':pesr,
						'beg_bal_sr':pesr,
						'pri_postings':pri_postings,
						'sec_postings':sec_postings,
						'phpe_postings_sr':phpe_postings_sr,
						'phpe_postings_pr':phpe_postings_pr,
						'diff_sr_pr':diff_sr_pr,
						'rev_beg_bal':rev_beg_bal,
						'diff1_pool':diff1_pool,
						'bal_ap':bal_ap,
						'bal_ap_pool':bal_ap_pool,
						'end_bal_pool':end_bal_pool,
						'diff_total_sec':diff_total_sec,
						'eba':end_bal_pool,
						'ebb':end_bal_pool,
						'ebc':end_bal_pool,
						}
				self.pool.get('new.reval.accts').write(cr, uid, acct,acctVals)
			pri_pf = pri_pool_amt / (pri_pool_amt + sec_pool_amt)
			sec_pf = sec_pool_amt / (pri_pool_amt + sec_pool_amt)
			pri_appf = pri_appool / (pri_appool + sec_appool) 
			sec_appf = sec_appool / (pri_appool + sec_appool)
			vals = {
					'pri_pool':pri_pool_amt,
					'sec_pool':sec_pool_amt,
					'pri_pf':pri_pf,
					'sec_pf':sec_pf,
					'pri_appool':pri_appool,
					'sec_appool':sec_appool,
					'pri_appf':pri_appf,
					'sec_appf':sec_appf,
					}
			self.write(cr, uid, ids, vals)
		return self.getRevaluatedAccounts(cr, uid, ids)
	
	def getRevaluatedAccounts(self, cr, uid, ids, context=None):
		for reval in self.read(cr, uid, ids, context=None):
			reval_id = reval['id']
			period_read = self.pool.get('account.period').read(cr, uid, reval['period_id'][0],['date_start','date_stop'])
			for acct in reval['acc_ids']:
				self.pool.get('new.reval.accts').unlink(cr, uid, acct)
			accts = self.pool.get('account.account').search(cr, uid, [('is_pr','=',True)])
			pri_pool_amt = 0.00
			sec_pool_amt = 0.00
			for acct in accts:
				acctReader = self.pool.get('account.account').read(cr, uid, acct, context=None)
				analyticAccSearch = self.pool.get('account.analytic.account').search(cr, uid, [('normal_account','=',acct)])
				for analyticAccount in analyticAccSearch:
					analyticReader = self.pool.get('account.analytic.account').read(cr, uid, analyticAccount, context=None)
					entriesSearch = self.pool.get('account.move.line').search(cr, uid, [('account_id','=',acct),('analytic_account_id','=',analyticAccount),('date','<',period_read['date_start'])])
					beg_bal_src = 0.00
					for entry in entriesSearch:
						entryReader = self.pool.get('account.move.line').read(cr, uid, entry, context=None)
						beg_bal_src += entryReader['debit'] - entryReader['credit']
					vals = {
						'reval_id':reval['id'],
						'account_id':acct,
						'acc_name':analyticReader['name'],
						'analytic_id':analyticAccount,
						'beg_bal_src':beg_bal_src,
						'beg_bal_phpe':beg_bal_src,
						'beg_bal_sr':beg_bal_src,
					}
					self.pool.get('new.reval.accts').create(cr, uid, vals)
		return self.rasr(cr, uid, ids)
	def rasr(self, cr, uid, ids, context=None):
		for reval in self.read(cr, uid, ids, context=None):
			reval_id = reval['id']
			period_read = self.pool.get('account.period').read(cr, uid, reval['period_id'][0],['date_start','date_stop'])
			sr = reval['rate_sre']
			pr = reval['rate_pre']
			er = reval['rate_ere']
			rcf1 = reval['rcf1']
			rcf2 = reval['rcf2']
			sec_pf = reval['sec_pf']
			sec_appf = reval['sec_appf']
			for acct in reval['acc_ids']:
				pri_postings = 0.00
				sec_postings = 0.00
				acctReader = self.pool.get('new.reval.accts').read(cr, uid, acct, context=None)
				entrySearch = self.pool.get('account.move.line').search(cr, uid, [('date','>=',period_read['date_start']),('date','<=',period_read['date_stop']),('account_id','=',acctReader['account_id'][0]),('analytic_account_id','=',acctReader['analytic_id'][0])])
				for entry in entrySearch:
					entryReader = self.pool.get('account.move.line').read(cr, uid, entry, context=None)
					if entryReader['currency_id'][0]==reval['secondary_curr'][0]:
						if entryReader['debit']>0.00:
							sec_postings +=entryReader['amount_currency']
						elif entryReader['credit']>0.00:
							sec_postings -=entryReader['amount_currency']
					elif entryReader['currency_id'][0]==reval['primary_curr'][0]:
						if entryReader['debit']>0.00:
							pri_postings +=entryReader['amount_currency']
						elif entryReader['credit']>0.00:
							pri_postings -=entryReader['amount_currency']
				phpe_postings_sr = pri_postings + (sec_postings / sr)
				phpe_postings_pr = pri_postings + (sec_postings / pr)
				diff_sr_pr = phpe_postings_pr -  phpe_postings_sr
				rev_beg_bal = acctReader['beg_bal_sr']+((acctReader['beg_bal_sr']*sec_pf)*rcf1)
				diff1 = (acctReader['beg_bal_sr']*sec_pf)*rcf1
				bal_ap = acctReader['beg_bal_src']+phpe_postings_pr
				bal_ap_diff1 = bal_ap + diff1
				diff2 = bal_ap_diff1 * sec_appf * rcf2
				end_bal_pr = bal_ap_diff1 + diff2
				post_corr = phpe_postings_pr - phpe_postings_sr
				diff_total_pr = diff1 + diff2
				eba = post_corr + diff_total_pr + phpe_postings_sr + acctReader['beg_bal_src']
				vals = {
					'pri_postings':pri_postings,
					'sec_postings':sec_postings,
					'phpe_postings_sr':phpe_postings_sr,
					'phpe_postings_pr':phpe_postings_pr,
					'diff_sr_pr':diff_sr_pr,
					'rev_beg_bal':rev_beg_bal,
					'diff1':diff1,
					'bal_ap':bal_ap,
					'bal_ap_diff1':bal_ap_diff1,
					'diff2':diff2,
					'end_bal_pr':end_bal_pr,
					'post_corr':post_corr,
					'diff_total_pr':diff_total_pr,
					'eba':eba,
					}
				self.pool.get('new.reval.accts').write(cr, uid, acct, vals)
		return True
	
	def get_poolaccts(self, cr, uid, ids, context=None):
		for reval in self.read(cr, uid, ids, context=None):
			reval_id = reval['id']
			period_read = self.pool.get('account.period').read(cr, uid, reval['period_id'][0],['date_start','date_stop'])
			for acct in reval['pool_ids']:
				self.pool.get('new.reval.accts').unlink(cr, uid, acct)
			accts = self.pool.get('account.account').search(cr, uid, [('include_pool','=',True)])
			pri_pool_amt = 0.00
			sec_pool_amt = 0.00
			for acct in accts:
				pri_pool=False
				sec_pool = False
				curr_id = False
				acctRead = self.pool.get('account.account').read(cr, uid, acct, ['name','currency_id'])
				if acctRead['currency_id']!=False:
					curr_id = acctRead['currency_id'][0]
				if curr_id != False:
					sec_pool = True
				elif curr_id ==False:
					pri_pool = True
				entries = self.pool.get('account.move.line').search(cr, uid, [('account_id','=',acct),('date','<',period_read['date_start'])])
				beg_bal_src = 0.00
				for entry in entries:
					entryRead = self.pool.get('account.move.line').read(cr, uid, entry, context=None)
					if entryRead['debit']>0.00:
						beg_bal_src+=entryRead['amount_currency']
					elif entryRead['credit']>0.00:
						beg_bal_src-=entryRead['amount_currency']
				vals = {
					'pool_id':reval['id'],
					'account_id':acct,
					'curr_id':curr_id,
					'pri_pool':pri_pool,
					'sec_pool':sec_pool,
					'acc_name':acctRead['name'],
					'beg_bal_src':beg_bal_src,
				}
				self.pool.get('new.reval.accts').create(cr, uid, vals)
		return self.pesr(cr, uid, ids)
	
	def revalAcctsGL(self, cr, uid, ids, context=None):
		for reval in self.read(cr, uid, ids, context=None):
			for acct in reval['acc_ids']:
				acctRead = self.pool.get('new.reval.accts').read(cr, uid, acct, context=None)
				if acctRead['analytic_id']==False:
					continue
				else:
					analyticRead = self.pool.get('account.analytic.account').read(cr, uid, acctRead['analytic_id'][0],['ntm_type','region_id'])
					ebb_amt = 0.00
					ebc_amt = 0.00
					if analyticRead['ntm_type']=='gl':
						regionRead = self.pool.get('region.config').read(cr, uid, analyticRead['region_id'][0],['gain_loss_acct'])
						if acctRead['analytic_id'][0]==regionRead['gain_loss_acct'][0]:
							analyticSearch = self.pool.get('account.analytic.account').search(cr, uid, [('region_id','=',analyticRead['region_id'][0])])
							for analyticItem in analyticSearch:
								analyticRead2 = self.pool.get('account.analytic.account').read(cr, uid, analyticItem, ['name'])
								revAcctSearch =  self.pool.get('new.reval.accts').search(cr, uid, [('analytic_id','=',analyticItem),('reval_id','=',reval['id'])])
								for revAcct in revAcctSearch:
									revAcctRead =  self.pool.get('new.reval.accts').read(cr, uid, revAcct,['diff_total_pr','post_corr'])
									ebc_amt += revAcctRead['post_corr']
									ebb_amt += revAcctRead['diff_total_pr']
						ebb_amt = ebb_amt + acctRead['beg_bal_src'] + acctRead['phpe_postings_sr']
						ebc_amt = ebc_amt + ebb_amt
					elif analyticRead['ntm_type'] in ['income','expense','equity']:
						ebb_amt = acctRead['beg_bal_src']+acctRead['phpe_postings_sr']+acctRead['post_corr']
						ebc_amt = acctRead['beg_bal_src']+acctRead['phpe_postings_sr']
					elif analyticRead['ntm_type'] in ['pat','project']:
						ebb_amt = acctRead['eba']
						ebc_amt = acctRead['eba']
					vals = {'ebb':ebb_amt,'ebc':ebc_amt}
					self.pool.get('new.reval.accts').write(cr, uid, acct, vals)
		return True
	
	def createJERegionAccts(self, cr, uid, ids, context=None):
		for reval in self.read(cr, uid, ids, context=None):
			moveTemplate = {
						'journal_id':reval['journal_id'][0],
						'period_id':reval['period_id'][0],
						'date':reval['date'],
						'ref':reval['name'],
						}
			move_id = self.pool.get('account.move').create(cr, uid, moveTemplate)
			entryTemplate = {
						'journal_id':reval['journal_id'][0],
						'period_id':reval['period_id'][0],
						'date':reval['date'],
						'currency_id':reval['primary_curr'][0],
						'move_id':move_id,
						}
			debitSum = 0.00
			creditSum = 0.00
			narration = 'Entry Details'
			for acct in reval['acc_ids']:
				acctRead = self.pool.get('new.reval.accts').read(cr, uid, acct, context=None)
				if acctRead['analytic_id']==False:
					continue
				else:
					acctEntries = self.pool.get('account.move.line').search(cr, uid, [('analytic_account_id','=',acctRead['analytic_id'][0])])
					balance = 0.00
					name = 'Difference for ' + acctRead['acc_name'] + ' account'
					for entry in acctEntries:
						entryReader = self.pool.get('account.move.line').read(cr, uid, entry, ['debit','credit'])
						balance +=entryReader['debit']-entryReader['credit']
					analyticRead = self.pool.get('account.analytic.account').read(cr, uid, acctRead['analytic_id'][0],['ntm_type','region_id'])
					if analyticRead['ntm_type'] in ['gl']:
						debit = 0.00
						credit = 0.00
						amount_curr = 0.00
						if acctRead['ebc']<0:
							debit = 0.00
							credit = (balance-acctRead['ebc'])
							amount_curr = credit
							creditSum +=amount_curr
						elif acctRead['ebc']>0:
							credit = 0.00
							debit = balance - acctRead['ebc']
							amount_curr=debit
							debitSum +=amount_curr
						entryTemplate.update({'account_id':acctRead['account_id'][0],'debit':debit,'credit':credit,'name':name,'amount_currency':amount_curr,'analytic_account_id':acctRead['analytic_id'][0]})
						forNarration = '\n' +acctRead['acc_name'] +' '+str(amount_curr)
						narration = narration + forNarration
						self.pool.get('account.move.line').create(cr, uid, entryTemplate)
			uidRead = self.pool.get('res.users').read(cr, uid, uid, ['company_id'])
			compRead = self.pool.get('res.company').read(cr, uid, uidRead['company_id'][0], ['def_gain_loss'])
			analyticRead2 = self.pool.get('account.analytic.account').read(cr, uid, compRead['def_gain_loss'][0],['normal_account'])
			if creditSum != 0.00:
				name = 'Regional Accounts Gains'
				entryTemplate.update({'account_id':analyticRead2['normal_account'][0],'debit':creditSum,'credit':0.00,'name':name,'amount_currency':creditSum,'analytic_account_id':compRead['def_gain_loss'][0],'narration':narration})
				self.pool.get('account.move.line').create(cr, uid, entryTemplate)
			if debitSum != 0.00:
				name = 'Regional Accounts Loses'
				entryTemplate.update({'account_id':analyticRead2['normal_account'][0],'debit':0.00,'credit':debitSum,'name':name,'amount_currency':debitSum,'analytic_account_id':compRead['def_gain_loss'][0],'narration':narration})
				self.pool.get('account.move.line').create(cr, uid, entryTemplate)
			self.write(cr, uid, ids, {'region_fgl_move_id':move_id})
		return True#self.createURGLEntry(cr, uid, ids)
		
	def createURGLEntry(self, cr, uid, ids, context=None):
		for reval in self.read(cr, uid, ids, context=None):
			moveTemplate = {
						'journal_id':reval['journal_id'][0],
						'period_id':reval['period_id'][0],
						'date':reval['date'],
						'ref':reval['name'],
						}
			move_id = self.pool.get('account.move').create(cr, uid, moveTemplate)
			entryTemplate = {
						'journal_id':reval['journal_id'][0],
						'period_id':reval['period_id'][0],
						'date':reval['date'],
						'currency_id':reval['primary_curr'][0],
						'move_id':move_id,
						}
			uidRead = self.pool.get('res.users').read(cr, uid, uid, ['company_id'])
			compRead = self.pool.get('res.company').read(cr, uid, uidRead['company_id'][0], ['def_gain_loss','ur_gain_loss'])
			defReader = self.pool.get('account.analytic.account').read(cr, uid, compRead['def_gain_loss'][0],['normal_account'])
			#defReaderacctEntries = self.pool.get('account.move.line').search(cr, uid, [('analytic_account_id','=',defReader['analytic_id'][0])])
			defReaderacctEntries = self.pool.get('account.move.line').search(cr, uid, [('analytic_account_id','=',compRead['def_gain_loss'][0])])
			defReaderBalance = 0.00
			urGainLossBalance = 0.00
			for entry in defReaderacctEntries:
				entryReader = self.pool.get('account.move.line').read(cr, uid, entry, ['debit','credit'])
				defReaderBalance +=entryReader['debit']-entryReader['credit']
			urReaderacctEntries = self.pool.get('account.move.line').search(cr, uid, [('account_id','=',compRead['ur_gain_loss'][0])])
			name = 'Regional Accounts Gains'
			entryTemplate.update({#'account_id':analyticRead2['normal_account'][0],
								'account_id':defReader['normal_account'][0],
								'debit':creditSum,
								'credit':0.00,
								'name':name,
								'amount_currency':creditSum,
								'analytic_account_id':compRead['def_gain_loss'][0],
								'narration':narration})
			self.pool.get('account.move.line').create(cr, uid, entryTemplate)
			self.write(cr, uid, ids, {'ugl_fgl_move_id':move_id})
		return True
		
	def createJEnonRegionAccts(self, cr, uid, ids, context=None):
		for reval in self.read(cr, uid, ids, context=None):
			moveTemplate = {
						'journal_id':reval['journal_id'][0],
						'period_id':reval['period_id'][0],
						'date':reval['date'],
						'ref':reval['name'],
						}
			move_id = self.pool.get('account.move').create(cr, uid, moveTemplate)
			entryTemplate = {
						'journal_id':reval['journal_id'][0],
						'period_id':reval['period_id'][0],
						'date':reval['date'],
						'currency_id':reval['primary_curr'][0],
						'move_id':move_id,
						}
			debitSum = 0.00
			creditSum = 0.00
			narration = 'Entry Details'
			for acct in reval['acc_ids']:
				acctRead = self.pool.get('new.reval.accts').read(cr, uid, acct, context=None)
				if acctRead['analytic_id']==False:
					continue
				else:
					analyticRead = self.pool.get('account.analytic.account').read(cr, uid, acctRead['analytic_id'][0],['ntm_type','region_id'])
					if analyticRead['ntm_type'] in ['pat','project']:
						debit = 0.00
						credit = 0.00
						amount_curr = 0.00
						if acctRead['diff_total_pr']<0:
							debit = 0.00
							credit = (acctRead['diff_total_pr'] + acctRead['post_corr']) * -1
							amount_curr = credit
							creditSum +=amount_curr
						elif acctRead['diff_total_pr']>0:
							credit = 0.00
							debit = acctRead['diff_total_pr'] + acctRead['post_corr']
							amount_curr=debit
							debitSum +=amount_curr
						name = 'Difference for ' + acctRead['acc_name'] + ' account'
						entryTemplate.update({'account_id':acctRead['account_id'][0],'debit':debit,'credit':credit,'name':name,'amount_currency':amount_curr,'analytic_account_id':acctRead['analytic_id'][0]})
						forNarration = '\n' +acctRead['acc_name'] +' '+str(amount_curr)
						narration = narration + forNarration
						self.pool.get('account.move.line').create(cr, uid, entryTemplate)
			uidRead = self.pool.get('res.users').read(cr, uid, uid, ['company_id'])
			compRead = self.pool.get('res.company').read(cr, uid, uidRead['company_id'][0], ['def_gain_loss'])
			analyticRead2 = self.pool.get('account.analytic.account').read(cr, uid, compRead['def_gain_loss'][0],['normal_account'])
			if creditSum != 0.00:
				name = 'PAT and Project Accounts Gains'
				entryTemplate.update({'account_id':analyticRead2['normal_account'][0],'debit':creditSum,'credit':0.00,'name':name,'amount_currency':creditSum,'analytic_account_id':compRead['def_gain_loss'][0],'narration':narration})
				self.pool.get('account.move.line').create(cr, uid, entryTemplate)
			if debitSum != 0.00:
				name = 'PAT and Project Accounts Loses'
				entryTemplate.update({'account_id':analyticRead2['normal_account'][0],'debit':0.00,'credit':debitSum,'name':name,'amount_currency':debitSum,'analytic_account_id':compRead['def_gain_loss'][0],'narration':narration})
				self.pool.get('account.move.line').create(cr, uid, entryTemplate)
			self.write(cr, uid, ids, {'nonregion_fgl_move_id':move_id})
		return self.createJERegionAccts(cr, uid, ids)
	
	def updateSOAs(self, cr, uid, ids, context=None):
		for reval in self.read(cr, uid, ids, context=None):
			for acct in reval['acc_ids']:
				acctReader = self.pool.get('new.reval.accts').read(cr, uid, acct, context=None)
				if acctReader['analytic_id']==False:
					continue
				else:
					self.generate_soa(cr, uid, ids)
					statementSearch = self.pool.get('account.soa').search(cr, uid, [('account_number','=',acctReader['analytic_id'][0]),('period_id','=',reval['period_id'][0])])
					if not statementSearch:
						continue
					elif statementSearch:
						self.pool.get('account.soa').update_lines(cr, uid, [statementSearch[0]])
						income = 0.00
						expense = 0.00
						prev_bal = acctReader['beg_bal_sr']
						ending_balance = 0.00
						if prev_bal < 0.00:
							prev_bal = prev_bal * -1
						else:
							prev_bal = prev_bal
						allEntries = self.pool.get('account.move.line').search(cr, uid, [('analytic_account_id','=',acctReader['analytic_id'][0]),('period_id','=',reval['period_id'][0])])
						for entry in allEntries:
							entryReader = self.pool.get('account.move.line').read(cr, uid, entry, ['debit','credit'])
							income += entryReader['credit']
							expense += entryReader['debit']
						inc_exp = income - expense
						allEntries = self.pool.get('account.move.line').search(cr, uid, [('analytic_account_id','=',acctReader['analytic_id'][0])])
						for entry in allEntries:
							entryReader = self.pool.get('account.move.line').read(cr, uid, entry, ['debit','credit'])
							ending_balance +=  entryReader['credit'] - entryReader['debit']
						self.pool.get('account.soa').write(cr, uid, statementSearch[0], {'prev_balance':prev_bal,'total_income':income,'total_expense':expense,'inc_exp':inc_exp,'end_balance':ending_balance})
			self.soa_report(cr, uid, ids)
		return True
		
	def soa_report(self,cr, uid, ids, context=None):
		for reval in self.read(cr, uid, ids, context=None):
			statements = self.pool.get('account.soa').search(cr, uid, [('period_id','=',reval['period_id'][0])])
			self.pool.get('account.soa').create_soa_attachment(cr, uid, statements)
		return True
	
	def generate_soa(self, cr, uid, ids, context=None):
		date = datetime.datetime.now()
		date_now = date.strftime("%Y/%m/%d %H:%M")
		for reval in self.read(cr, uid, ids, context=None):
			for aa in self.pool.get('account.analytic.account').search(cr, uid, [('report','=','soa')]):
				statement = self.pool.get('account.soa').search(cr, uid, [('period_id','=',reval['period_id'][0]),('account_number','=',aa)])
				if not statement:
					values = {
						'date':date_now,
						'account_number':aa,
						'period_id':reval['period_id'][0]
						}
					self.pool.get('account.soa').create(cr, uid, values)
		return True
											
new_reval2()


class new_reval_send(osv.osv_memory):
	_name = 'new.reval.send'
	_description = "Revaluated SOA Sender"
	_columns = {
		'email':fields.many2one('email_template.account','Email Sender', required=True),
		}
	def sendEmails(self, cr, uid, ids, context=None):
		for sender in self.read(cr, uid, ids, context=context):
			revalReader = self.pool.get('new.reval').read(cr, uid, context['active_id'], context=None)
			for acct in revalReader['acc_ids']:
				accReader = self.pool.get('new.reval.accts').read(cr, uid, acct, context=None)
				if accReader['analytic_id']==False:
					continue
				else:
					checkAnalytic = self.pool.get('account.analytic.account').read(cr, uid, accReader['analytic_id'][0],['report','partner_id'])
					if checkAnalytic['report']=='soa':
						emailAddresses = ''
						emailChecker = self.pool.get('res.partner.address').search(cr, uid, [('partner_id','=',checkAnalytic['partner_id'][0]),('email','!=',False)])
						for email in emailChecker:
							emailReader = self.pool.get('res.partner.address').read(cr, uid, email, ['email'])
							if emailAddresses=='':
								emailAddresses = emailReader['email']
							elif emailAddresses!='':
								emailAddresses = emailAddresses +','+emailReader['email']
						check_soa = self.pool.get('account.soa').search(cr, uid, [('account_number','=',accReader['analytic_id'][0]),('period_id','=',revalReader['period_id'][0])])
						for soa_id in check_soa:
							#smtp_acct = sender['email']
							account_id = sender['email']
							subject = 'Revaluated SOA: '+ accReader['acc_name']
							email_to = emailAddresses
							values = {
								'account_id':account_id,
								'email_to':email_to,
								'folder':'outbox',
								'subject':subject,
								'state':'na',
								'server_ref':0,
								}
							email_lists = []
							email_created = self.pool.get('email_template.mailbox').create(cr, uid, values)
							email_lists.append(email_created)
							soa_attachments = self.pool.get('ir.attachment').search(cr, uid, [('res_model','=','account.soa'),('res_id','=',soa_id)])
							for soa_attachment in soa_attachments:
								query = ("""insert into mail_attachments_rel(mail_id, att_id)values(%s,%s)"""%(email_created,soa_attachment))
								cr.execute(query)
							self.pool.get('email_template.mailbox').send_this_mail(cr, uid, email_lists)
		return True
new_reval_send()

class account_period(osv.osv):
    _inherit = 'account.period'
    
    def revaluate_period(self, cr, uid, ids, context=None):
        for period in self.read(cr, uid, ids, context=None):
            period_id = period['id']
            checkReval=self.pool.get('new.reval').search(cr, uid, [('period_id','=',period_id)])
            if not checkReval:
                return {
                    'name': 'Revaluate',
                    'view_type':'form',
                    'nodestroy': True,
                    'target': 'new',
                    'view_mode':'form',
                    'res_model':'new.reval',
                    'type':'ir.actions.act_window',
                    'context':{'default_period_id':period_id},}
            elif checkReval:
                raise osv.except_osv(_('Warning!'), _('There is an existing revaluation document for this period!'))
account_period()
