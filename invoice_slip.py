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
                account_search = self.pool.get('account.account').search(cr, uid,['|',('code','=',regional_entries_read['acctid']),('code_accpac','=',regional_entries_read['acctid'])])
                if not account_search:
                    analytic_search = self.pool.get('account.analytic.account').search(cr, uid,['|',('code','=',regional_entries_read['acctid']),('code_accpac','=',regional_entries_read['acctid'])])
                    if not analytic_search:
                        raise osv.except_osv(_('Error !'), _('Account ID not existing!'))
                    elif analytic_search:
                        for analytic in analytic_search:
                            analytic_id = analytic
                            analytic_read = self.pool.get('account.analytic.account').read(cr, uid, analytic, ['normal_account'])
                            account_id = analytic_read['normal_account'][0]
                elif account_search:
                    for account in account_search:
                        account_id = account
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
                move_line = {
                    'name':regional_entries_read['transdesc'],
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':account_id,
                    'credit':credit,
                    'debit':debit,
                    'analytic_account_id':analytic_read['id'],
                    'date':regional_entries_read['date'],
                    'ref':regional_entries_read['ref'],
                    'move_id':move_id,
                    'amount_currency':regional_entries_read['scuramt'],
                    'currency_id':curr_id,
                    }
                self.pool.get('account.move.line').create(cr, uid, move_line)
                print regional_entry
                self.pool.get('regional.uploader').write(cr, uid, regional_entry, {'uploaded':True})
            self.pool.get('account.move').post(cr, uid, [move_id])
        return {'type': 'ir.actions.act_window_close'}
regional_upload()