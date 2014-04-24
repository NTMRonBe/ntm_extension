import time
from osv import osv, fields, orm
import netsvc
import pooler
import datetime
import psycopg2
from tools.translate import _

class regional_uploader(osv.osv):
    _name = 'regional.uploader'
    _columns = {
        'acctid':fields.char('Acct ID',size=32),
        'scuramt':fields.float('Amount'),
        'currency':fields.char('Currency',size=32),
        'ref':fields.char('Transref',size=64),
        'transdesc':fields.char('Description',size=64),
        'date':fields.date('Date'),
        'uploaded':fields.boolean('Uploaded'),
        'no_match':fields.boolean('No Match'),
        }
regional_uploader()

class regional_upload(osv.osv_memory):
    
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    
    _name = 'regional.upload'
    _columns = {
    'trans_nbr': fields.integer('# of Transaction', readonly=True),
    'credit': fields.float('Credit amount', readonly=True),
    'debit': fields.float('Debit amount', readonly=True),
    'journal_id':fields.many2one('account.journal','Effective Journal', required=True),
	'period_id':fields.many2one('account.period','Effective Period', required=True),
	'date':fields.date('Effective Date', required=True),
    'name':fields.char('Reference',size=64, required=True),
	}
    
    _defaults = {
        'date':lambda *a: time.strftime('%Y-%m-%d'),
        'period_id':_get_period,         
        }
    
    def default_get(self, cr, uid, fields, context=None):
        res = super(regional_upload, self).default_get(cr, uid, fields, context=context)
        data = self.trans_rec_get(cr, uid, context['active_ids'], context)
        if 'trans_nbr' in fields:
            res.update({'trans_nbr':data['trans_nbr']})
        if 'credit' in fields:
            res.update({'credit':data['credit']})
        if 'debit' in fields:
            res.update({'debit':data['debit']})
        return res

    def trans_rec_get(self, cr, uid, ids, context=None):
        account_move_line_obj = self.pool.get('regional.uploader')
        if context is None:
            context = {}
        credit = debit = 0
        account_id = False
        count = 0
        for line in account_move_line_obj.browse(cr, uid, context['active_ids'], context=context):
            count += 1
            if line.scuramt <0.00:
                credit +=line.scuramt
            elif line.scuramt>0.00:
                debit += line.scuramt
        creditChecker = credit*-1
        if creditChecker!=debit:
            raise osv.except_osv(_('Error !'), _('Make sure that all entries has a corresponding entry!'))
        return {'trans_nbr': count, 'credit': credit, 'debit': debit}

    
    def upload(self, cr, uid, ids, context=None):
        regional_entries = self.pool.get('regional.uploader').search(cr, uid, [('uploaded','=',False)])
	period_id = False
	date_now = False
	for form in self.read(cr, uid, ids, context=None):
	    period_id = form['period_id']
	    date_now = form['date']
        if regional_entries:
            date = datetime.datetime.now()
            journal_search = self.pool.get('account.journal').search(cr, uid, [('type','=','regional_report')],limit=1)
            journal_id = False
            for journal in journal_search:
                journal_id = journal
            move = {
                'journal_id':journal_id,
                'period_id':period_id,
                'date':date_now
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            for regional_entry in regional_entries:
                curr_id = False
                account_id = False
                analytic_id = False
                account_search = False
                analytic_search = False
                regional_entries_read = self.pool.get('regional.uploader').read(cr, uid, regional_entry,context=None)
                print regional_entries_read
                account_search = self.pool.get('account.accpac').search(cr, uid,[('name','=',regional_entries_read['acctid'])])
                accpac_acc = regional_entries_read['acctid']
                if not account_search:
                    accSearchNormal = self.pool.get('account.account').search(cr, uid, [('code','=',regional_entries_read['acctid'])])
                    if not accSearchNormal:
                        accSearchAnalytic = self.pool.get('account.analytic.account').search(cr, uid, [('code','=',regional_entries_read['acctid'])])
                        if not accSearchAnalytic:
                            raise osv.except_osv(_('Error !'), _('Account %s is not on the list of any accounts!')%accpac_acc)
                        elif accSearchAnalytic:
                            analyticRead = self.pool.get('account.analytic.account').read(cr, uid, accSearchAnalytic[0],['normal_account'])
                            analytic_id = accSearchAnalytic[0]
                            account_id = analyticRead['normal_account'][0]
                    elif accSearchNormal:
                        account_id = accSearchNormal[0]
                elif account_search:
                    acc_read = self.pool.get('account.accpac').read(cr, uid, account_search[0], context=None)
                    if acc_read['account_id']:
                        account_id = acc_read['account_id'][0]
                    elif acc_read['analytic_id']:
                        analyticRead = self.pool.get('account.analytic.account').read(cr, uid, acc_read['analytic_id'][0],['normal_account'])
                        analytic_id = acc_read['analytic_id'][0]
                        account_id = analyticRead['normal_account'][0]
                curr_search = self.pool.get('res.currency').search(cr, uid, [('name','ilike',regional_entries_read['currency'])])
                for currency in curr_search:
                    curr_id = currency
                currency_read = self.pool.get('res.currency').read(cr, uid, curr_id, ['rate'])
                amount = regional_entries_read['scuramt'] / currency_read['rate']
                credit = 0.00
                debit = 0.00
                if amount > 0.00:
                    credit = 0.00
                    debit = amount
                elif amount < 0.00:
                    credit = amount * -1
                    debit = 0.00
                name = regional_entries_read['transdesc'] +' '+regional_entries_read['date']
		move_line = {
                    'name':name,
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':account_id,
                    'credit':credit,
                    'debit':debit,
                    'analytic_account_id':analytic_id,
                    'date':regional_entries_read['date'],
                    'ref':regional_entries_read['ref'],
                    'move_id':move_id,
                    'amount_currency':regional_entries_read['scuramt'],
                    'currency_id':curr_id,
                    }
                self.pool.get('account.move.line').create(cr, uid, move_line)
                self.pool.get('regional.uploader').write(cr, uid, regional_entry, {'uploaded':True})
            #self.pool.get('account.move').post(cr, uid, [move_id])
        return {'type': 'ir.actions.act_window_close'}
regional_upload()