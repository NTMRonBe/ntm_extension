import time
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
	_columns = {
		'name':fields.char('Revaluation ID', size=64),
		'period_id':fields.many2one('account.period', 'Revaluated Period'),
		'rate_sr':fields.float('Start Rate'),
		'rate_pr':fields.float('Post Rate'),
		'rate_er':fields.float('End Rate'),
		'rate_sre':fields.function(_compute_sre_amount, method=True, type='float', string='Start Rate', store=False,digits=(16,8)),
		'rate_pre':fields.function(_compute_pre_amount, method=True, type='float', string='Post Rate', store=False,digits=(16,8)),
		'rate_ere':fields.function(_compute_ere_amount, method=True, type='float', string='End Rate', store=False,digits=(16,8)),
		'primary_curr':fields.many2one('res.currency','Currency'),
		'secondary_curr':fields.many2one('res.currency','Currency'),
		'pri_pool':fields.float('Money Pool',digits=(16,8)),
		'sec_pool':fields.float('Money Pool'),
		'pri_appool':fields.float('Money Pool'),
		'sec_appool':fields.float('Money Pool'),
		'pool_total':fields.float('Total Money Pool'),
		'pool_aptotal':fields.float('Total Money Pool(After Posting)'),
		'pri_pf':fields.float('Portion Factor',digits=(16,8)),
		'sec_pf':fields.float('Portion Factor',digits=(16,8)),
		'pri_appf':fields.float('Portion Factor',digits=(16,8)),
		'sec_appf':fields.float('Portion Factor',digits=(16,8)),
		'rcf1':fields.function(_rcf1_amount, method=True, type='float', string='Rate Change Factor 1', store=False,digits=(16,8)),
		'rcf2':fields.function(_rcf2_amount, method=True, type='float', string='Rate Change Factor 2', store=False,digits=(16,8)),
		'move_id':fields.many2one('account.move','Journal Entry'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
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
		#'eba':fields.function(_eba_amount, method=True, type='float', string='EB A.', store=False),
		#'ebb':fields.function(_ebb_amount, method=True, type='float', string='EB B.', store=False),
		}
new_reval_accts()

class new_reval2(osv.osv):
	_inherit = 'new.reval'
	_columns = {
		'acc_ids':fields.one2many('new.reval.accts','reval_id','Accounts for Revaluation'),
		}
		
	def get_pool_accts(self, cr, uid, ids, context=None):
		userRead = self.pool.get('res.users').read(cr, uid, uid, ['company_id'])
		companyRead = self.pool.get('res.company').read(cr, uid, userRead['company_id'][0],['currency_id'])
		for reval in self.read(cr, uid, ids, context=None):
			reval_period = reval['period_id'][0]
			beg_period = reval_period - 1
			start_rate = reval['rate_sr']
			post_rate = reval['rate_pr']
			end_rate = reval['rate_er']
			sre_rate = reval['rate_sre']
			ere_rate = reval['rate_ere']
			rcf1 = reval['rcf1']
			rcf2 = reval['rcf2']
			sec_appf = reval['sec_appf']
			primary_pool = 0.00
			secondary_pool = 0.00
			primary_appool = 0.00
			secondary_appool = 0.00
			for accts in reval['acc_ids']:
				self.pool.get('new.reval.accts').unlink(cr, uid, accts)
			accts = self.pool.get('account.account').search(cr, uid, [('include_pool','=',True)])
			for acct in accts:
				pri_pool = False
				sec_pool = False
				curr_id = False
				acctRead = self.pool.get('account.account').read(cr, uid, acct,['name','currency_id'])
				if acctRead['currency_id']!=False:
					curr_id = acctRead['currency_id'][0]
				if curr_id != False:
					sec_pool = True
				elif curr_id ==False:
					pri_pool = True
				vals = {
					'reval_id':reval['id'],
					'account_id':acct,
					'curr_id':curr_id,
					'pri_pool':pri_pool,
					'sec_pool':sec_pool,
				}
				analytic_acc_search = self.pool.get('account.analytic.account').search(cr, uid, [('normal_account','=',acct)])
				phpe_sr = 0.00
				if analytic_acc_search:
					for analytic_acc in analytic_acc_search:
						analyticRead = self.pool.get('account.analytic.account').read(cr, uid, analytic_acc, ['name']),
						analyticName = analyticRead[0]['name']
						entries = self.pool.get('account.move.line').search(cr, uid, [('analytic_account_id','=',analytic_acc),('account_id','=',acct), ('period_id','<', reval_period)])
						amount = 0.00
						for entry in entries:
							entryRead = self.pool.get('account.move.line').read(cr, uid, entry, ['debit','credit','amount_currency'])
							if entryRead['debit']>0.00:
								amount +=entryRead['amount_currency']
							elif entryRead['credit']>0.00:
								amount -=entryRead['amount_currency']
						if sec_pool == True:
							phpe_sr = amount * start_rate
						else:
							phpe_sr = amount
						entries_rev = self.pool.get('account.move.line').search(cr, uid, [('analytic_account_id','=',analytic_acc),('account_id','=',acct),('period_id','=',reval_period)])
						rev_amount = 0.00
						pri_posts = 0.00
						sec_posts = 0.00
						for entry_rev in entries_rev:
							entryRevRead = self.pool.get('account.move.line').read(cr, uid, entry_rev,['debit','credit','currency_id','amount_currency'])
							if entryRevRead['debit']>0.00:
								rev_amount +=entryRevRead['amount_currency']
							elif entryRevRead['credit']>0.00:
								rev_amount -=entryRevRead['amount_currency']
						rev_beg_bal = 0.00
						diff1_pool = 0.00
						bal_ap_pool = 0.00
						if sec_pool == True:
							pri_posts = 0.00
							sec_posts = rev_amount
							rev_beg_bal = phpe_sr + (phpe_sr * rcf1)
							secondary_pool += phpe_sr
							diff1_pool = phpe_sr * rcf1
						else:
							pri_posts = rev_amount
							sec_posts = 0.00
							rev_beg_bal = phpe_sr
							primary_pool += phpe_sr
						phpe_postings_sr = sec_posts * start_rate
						phpe_postings_pr = sec_posts * post_rate
						phpe_postings_sr = phpe_postings_sr + pri_posts
						phpe_postings_pr = phpe_postings_pr + pri_posts
						diff_sr_pr = phpe_postings_pr - phpe_postings_sr
						bal_ap = phpe_sr + phpe_postings_sr
						end_bal_pool = 0.00
						if sec_pool == True:
							bal_ap_pool = (amount + sec_posts) * post_rate
							secondary_appool += bal_ap
							end_bal_pool = (amount + sec_posts) * end_rate
							diff_total_sec = (amount+sec_posts)*((1/ere_rate)-(1/sre_rate))
						else:
							bal_ap_pool = amount + phpe_postings_pr
							primary_appool += bal_ap
							end_bal_pool = amount + phpe_postings_pr
							diff_total_sec = 0.00
						diff2 = 0.00 * sec_appf * rcf2
						eba = 0.00
						if sec_pool == True:
							eba = (amount + sec_posts) * end_rate
						elif pri_pool == True:
							eba = amount + phpe_postings_pr
						vals.update({'analytic_id':analytic_acc, 'acc_name':analyticName, 'beg_bal_src':amount,'beg_bal_sr':phpe_sr, 'beg_bal_phpe':phpe_sr,'pri_postings':pri_posts,'sec_postings':sec_posts,'phpe_postings_sr':phpe_postings_sr,'phpe_postings_pr':phpe_postings_pr,'diff_sr_pr':diff_sr_pr,'rev_beg_bal':rev_beg_bal, 'diff1_pool':diff1_pool,'bal_ap':bal_ap,'bal_ap_pool':bal_ap_pool,'diff2':diff2, 'end_bal_pool':end_bal_pool,'diff_total_sec':diff_total_sec})
						self.pool.get('new.reval.accts').create(cr, uid, vals)
				elif not analytic_acc_search:
					entries = self.pool.get('account.move.line').search(cr, uid, [('account_id','=',acct), ('period_id','<', reval_period)])
					amount = 0.00
					rev_amount = 0.00
					for entry in entries:
						entryRead = self.pool.get('account.move.line').read(cr, uid, entry, ['debit','credit','amount_currency'])
						if entryRead['debit']>0.00:
							amount +=entryRead['amount_currency']
						elif entryRead['credit']>0.00:
							amount -=entryRead['amount_currency']
						if sec_pool == True:
							phpe_sr = amount * start_rate
						else:
							phpe_sr = amount
					entries_rev = self.pool.get('account.move.line').search(cr, uid, [('account_id','=',acct),('period_id','=',reval_period)])
					pri_posts = 0.00
					sec_posts = 0.00
					rev_beg_bal = 0.00
					diff1_pool = 0.00
					bal_ap_pool = 0.00
					for entry_rev in entries_rev:
						entryRevRead = self.pool.get('account.move.line').read(cr, uid, entry_rev,['debit','credit','currency_id','amount_currency'])
						if entryRevRead['debit']>0.00:
							rev_amount +=entryRevRead['amount_currency']
						elif entryRevRead['credit']>0.00:
							rev_amount -=entryRevRead['amount_currency']
					if sec_pool == True:
						pri_posts = 0.00
						sec_posts = rev_amount
						rev_beg_bal = phpe_sr + (phpe_sr * rcf1)
						secondary_pool += phpe_sr
						diff1_pool = phpe_sr * rcf1
					else:
						rev_beg_bal = phpe_sr
						pri_posts = rev_amount
						sec_posts = 0.00
						primary_pool += phpe_sr
					phpe_postings_sr = sec_posts * start_rate
					phpe_postings_pr = sec_posts * post_rate
					phpe_postings_sr = phpe_postings_sr + pri_posts
					phpe_postings_pr = phpe_postings_pr + pri_posts
					diff_sr_pr = phpe_postings_pr - phpe_postings_sr
					bal_ap = phpe_sr + phpe_postings_sr
					diff_total_sec = 0.00
					if sec_pool == True:
						bal_ap_pool = (amount + sec_posts) * post_rate
						secondary_appool += bal_ap_pool
						end_bal_pool = (amount + sec_posts) * end_rate
						diff_total_sec = (amount+sec_posts)*((1/ere_rate)-(1/sre_rate))
					else:
						bal_ap_pool = amount + phpe_postings_pr
						primary_appool += bal_ap_pool
						end_bal_pool = amount + phpe_postings_pr
						diff_total_sec = 0.00
					eba = 0.00
					if sec_pool == True:
						eba = (amount + sec_posts) * end_rate
					elif pri_pool == True:
						eba = amount + phpe_postings_pr
					vals.update({'acc_name':acctRead['name'],'beg_bal_src':amount,'beg_bal_sr':phpe_sr, 'beg_bal_phpe':phpe_sr,'pri_postings':pri_posts,'sec_postings':sec_posts,'phpe_postings_sr':phpe_postings_sr,'phpe_postings_pr':phpe_postings_pr,'diff_sr_pr':diff_sr_pr,'rev_beg_bal':rev_beg_bal,'diff1_pool':diff1_pool,'bal_ap':bal_ap,'bal_ap_pool':bal_ap_pool, 'end_bal_pool':end_bal_pool,'diff_total_sec':diff_total_sec, 'eba':eba,'ebb':eba,'ebc':eba})
					self.pool.get('new.reval.accts').create(cr, uid, vals)
			pool_total = primary_pool + secondary_pool
			pool_aptotal = primary_appool + secondary_appool
			pri_pf = primary_pool / pool_total
			sec_pf = secondary_pool / pool_total
			pri_appf = primary_appool / pool_aptotal
			sec_appf = secondary_appool / pool_aptotal
			self.write(cr, uid, ids, {'pri_pool':primary_pool,'sec_pool':secondary_pool,'pool_total':pool_total,'pri_pf':pri_pf,'sec_pf':sec_pf, 'pri_appool':primary_appool,'sec_appool':secondary_appool,'pool_aptotal':pool_aptotal, 'pri_appf':pri_appf,'sec_appf':sec_appf})
		return self.getRevaluatedAccts(cr, uid, ids)
		
	def getRevaluatedAccts(self, cr, uid, ids, context=None):
		userRead = self.pool.get('res.users').read(cr, uid, uid, ['company_id'])
		companyRead = self.pool.get('res.company').read(cr, uid, userRead['company_id'][0],['currency_id'])
		for reval in self.read(cr, uid, ids, context=None):
			reval_period = reval['period_id'][0]
			start_rate = reval['rate_sr']
			post_rate = reval['rate_pr']
			rcf1 = reval['rcf1']
			sec_pf = reval['sec_pf']
			rcf2 = reval['rcf2']
			sec_appf = reval['sec_appf']
			beg_period = reval_period - 1
			accts = self.pool.get('account.account').search(cr, uid, [('is_pr','=',True)])
			for acct in accts:
				acctRead = self.pool.get('account.account').read(cr, uid, acct,['name','currency_id'])
				vals = {
					'reval_id':reval['id'],
					'account_id':acct,
					'is_pr':True,
				}
				analytic_acc_search = self.pool.get('account.analytic.account').search(cr, uid, [('normal_account','=',acct)])
				if analytic_acc_search:
					for analytic_acc in analytic_acc_search:
						analyticRead = self.pool.get('account.analytic.account').read(cr, uid, analytic_acc, ['name','ntm_type']),
						print analyticRead
						analyticName = analyticRead[0]['name']
						entries = self.pool.get('account.move.line').search(cr, uid, [('analytic_account_id','=',analytic_acc),('account_id','=',acct), ('period_id','<', reval_period)])
						amount = 0.00
						for entry in entries:
							entryRead = self.pool.get('account.move.line').read(cr, uid, entry, ['debit','credit','amount_currency'])
							if entryRead['debit']>0.00:
								amount +=entryRead['amount_currency']
							elif entryRead['credit']>0.00:
								amount -=entryRead['amount_currency']
						entries_rev = self.pool.get('account.move.line').search(cr, uid, [('analytic_account_id','=',analytic_acc),('account_id','=',acct),('period_id','=',reval_period)])
						rev_amount = 0.00
						pri_posts = 0.00
						sec_posts = 0.00
						for entry_rev in entries_rev:
							entryRevRead = self.pool.get('account.move.line').read(cr, uid, entry_rev,['debit','credit','currency_id','amount_currency'])
							if entryRevRead['currency_id'][0]==companyRead['currency_id'][0]:
								if entryRevRead['debit']>0.00:
									pri_posts += entryRevRead['amount_currency']
								elif entryRevRead['credit']>0.00:
									pri_posts -= entryRevRead['amount_currency']
							elif entryRevRead['currency_id'][0]!=companyRead['currency_id'][0]:
								if entryRevRead['debit']>0.00:
									sec_posts += entryRevRead['amount_currency']
								elif entryRevRead['credit']>0.00:
									sec_posts -= entryRevRead['amount_currency']
						phpe_postings_sr = sec_posts * start_rate
						phpe_postings_pr = sec_posts * post_rate
						phpe_postings_sr = phpe_postings_sr + pri_posts
						phpe_postings_pr = phpe_postings_pr + pri_posts
						diff_sr_pr = phpe_postings_pr - phpe_postings_sr
						rev_beg_bal = amount + (amount*sec_pf*rcf1)
						diff1 = amount * sec_pf * rcf1
						bal_ap = amount + phpe_postings_pr
						bal_ap_diff1 = amount + phpe_postings_pr + diff1
						diff2 = bal_ap_diff1 * sec_appf * rcf2
						end_bal_pr = bal_ap_diff1 + diff2
						post_corr = phpe_postings_pr - phpe_postings_sr
						diff_total_pr = diff1 + diff2
						eba = amount+ phpe_postings_sr+ post_corr+ diff_total_pr
						ebb = 0.00
						ebc = 0.00
						if analyticRead[0]['ntm_type'] in ['equity','income','expense']:
							ebb = amount + phpe_postings_sr + post_corr
							ebc = amount + phpe_postings_sr
						elif analyticRead[0]['ntm_type'] not in ['equity','income','expense','gl']:
							ebb = eba
							ebc = eba
						vals.update({'analytic_id':analytic_acc, 'acc_name':analyticName, 'beg_bal_src':amount,'beg_bal_sr':amount, 'beg_bal_phpe':amount,'pri_postings':pri_posts,'sec_postings':sec_posts,'phpe_postings_sr':phpe_postings_sr,'phpe_postings_pr':phpe_postings_pr,'diff_sr_pr':diff_sr_pr,'rev_beg_bal':rev_beg_bal,'diff1':diff1,'bal_ap':bal_ap,'bal_ap_diff1':bal_ap_diff1,'diff2':diff2,'end_bal_pr':end_bal_pr,'post_corr':post_corr, 'diff_total_pr':diff_total_pr, 'eba':eba, 'ebb':ebb, 'ebc':ebc})
						self.pool.get('new.reval.accts').create(cr, uid, vals)
				elif not analytic_acc_search:
					entries = self.pool.get('account.move.line').search(cr, uid, [('account_id','=',acct), ('period_id','<', reval_period)])
					amount = 0.00
					for entry in entries:
						entryRead = self.pool.get('account.move.line').read(cr, uid, entry, ['debit','credit','amount_currency'])
						if entryRead['debit']>0.00:
							amount +=entryRead['amount_currency']
						elif entryRead['credit']>0.00:
							amount -=entryRead['amount_currency']
					entries_rev = self.pool.get('account.move.line').search(cr, uid, [('account_id','=',acct),('period_id','=',reval_period)])
					rev_amount = 0.00
					pri_posts = 0.00
					sec_posts = 0.00
					for entry_rev in entries_rev:
						entryRevRead = self.pool.get('account.move.line').read(cr, uid, entry_rev,['debit','credit','currency_id','amount_currency'])
						if entryRevRead['currency_id'][0]==companyRead['currency_id'][0]:
							if entryRevRead['debit']>0.00:
								pri_posts += entryRevRead['amount_currency']
							elif entryRevRead['credit']>0.00:
								pri_posts -= entryRevRead['amount_currency']
						elif entryRevRead['currency_id'][0]!=companyRead['currency_id'][0]:
							if entryRevRead['debit']>0.00:
								sec_posts += entryRevRead['amount_currency']
							elif entryRevRead['credit']>0.00:
								sec_posts -= entryRevRead['amount_currency']
					phpe_postings_sr = sec_posts * start_rate
					phpe_postings_pr = sec_posts * post_rate
					phpe_postings_sr = phpe_postings_sr + pri_posts
					phpe_postings_pr = phpe_postings_pr + pri_posts
					diff_sr_pr = phpe_postings_pr - phpe_postings_sr
					rev_beg_bal = amount + (amount*sec_pf*rcf1)
					diff1 = amount * sec_pf * rcf1
					bal_ap = amount + phpe_postings_pr
					bal_ap_diff1 = amount + phpe_postings_pr + diff1
					diff2 = bal_ap_diff1 * sec_appf * rcf2
					end_bal_pr = bal_ap_diff1 + diff2
					post_corr = phpe_postings_pr - phpe_postings_sr
					diff_total_pr = diff1 + diff2
					eba = amount+ phpe_postings_sr+ post_corr+ diff_total_pr
					vals.update({'acc_name':acctRead['name'],'beg_bal_src':amount,'beg_bal_sr':amount, 'beg_bal_phpe':amount,'pri_postings':pri_posts,'sec_postings':sec_posts,'phpe_postings_sr':phpe_postings_sr,'phpe_postings_pr':phpe_postings_pr,'diff_sr_pr':diff_sr_pr,'rev_beg_bal':rev_beg_bal,'diff1':diff1,'bal_ap':bal_ap,'bal_ap_diff1':bal_ap_diff1,'diff2':diff2,'end_bal_pr':end_bal_pr,'post_corr':post_corr, 'diff_total_pr':diff_total_pr, 'eba':eba, 'ebb':eba, 'ebc':eba})
					self.pool.get('new.reval.accts').create(cr, uid, vals)
		return True
new_reval2()