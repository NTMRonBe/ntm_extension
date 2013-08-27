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

class regional_upload(osv.osv):
    _name = 'regional.upload'
    def upload(self, cr, uid, ids, context=None):
        regional_entries = self.pool.get('regional.uploader').search(cr, uid, [('uploaded','=',False)])
        if regional_entries:
            date = datetime.datetime.now()
            period = date.strftime("%m/%Y")
            date_now = date.strftime("%Y/%m/%d")
            period_search = self.pool.get('account.period').search(cr, uid, [('name','=',period)])
            journal_search = self.pool.get('account.journal').search(cr, uid, [('type','=','regional_report')],limit=1)
            journal_id = False
            period_id = False
            for journal in journal_search:
                journal_id = journal
            for period in period_search:
                period_id = period
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