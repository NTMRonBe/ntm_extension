import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
from datetime import datetime
from dateutil.relativedelta import relativedelta

class recur_secondary_curr(osv.osv):
    _name = 'recur.secondary.curr'
    _description = "Secondary Currency Recurring Entries"
    _columns = {
        'name':fields.char('Name', size=64, required=True),
        'journal_id':fields.many2one('account.journal','Journal', required=True),
        'currency_id':fields.many2one('res.currency', 'Currency', required=True),
        'state': fields.selection([('draft','Draft'),('running','Running'),('done','Done')], 'State', required=True, readonly=True),
        'acct_selection':fields.selection([('normal','Normal Accounts'),('analytic','Analytic Accounts')], 'Involved Accounts', required=True)
        }
    
    _defaults = {
        'state':'draft'
    }
recur_secondary_curr()

class recur_secondary_curr_line(osv.osv):
    _name = 'recur.secondary.curr.line'
    _description = "Recurring Lines"
    _columns = {
        'name':fields.char('Name',size=64, required=True),
        'account_id':fields.many2one('account.account','Normal Account'),
        'analytic_id':fields.many2one('account.analytic.account','Analytic Account'),
        'recur_id':fields.many2one('recur.secondary.curr','Recurring ID'),
        'debit':fields.float('Debit'),
        'credit':fields.float('Credit'),
        }
recur_secondary_curr_line()

class recur_secondary_curr_sched(osv.osv):
    _name = "recur.secondary.curr.sched"
    _description = "Schedule"
    _columns = {
        'recur_id': fields.many2one('recur.secondary.curr', 'Recurring ID', required=True, select=True, ondelete='cascade'),
        'date': fields.date('Date', required=True),
        'move_id': fields.many2one('account.move', 'Entry'),
    }

    def move_create(self, cr, uid, ids, context=None):
        tocheck = {}
        all_moves = []
        obj_model = self.pool.get('account.model')
        for line in self.browse(cr, uid, ids, context=context):
            datas = {
                'date': line.date,
            }
            move_ids = obj_model.generate(cr, uid, [line.subscription_id.model_id.id], datas, context)
            tocheck[line.subscription_id.id] = True
            self.write(cr, uid, [line.id], {'move_id':move_ids[0]})
            all_moves.extend(move_ids)
        if tocheck:
            self.pool.get('account.subscription').check(cr, uid, tocheck.keys(), context)
        return all_moves

    _rec_name = 'date'
recur_secondary_curr_sched()

class rsc(osv.osv):
    _inherit = 'recur.secondary.curr'
    _columns = {
        'line_ids':fields.one2many('recur.secondary.curr.line','recur_id', 'Entry Lines'),
        'sched_ids':fields.one2many('recur.secondary.curr.sched','recur_id', 'Schedule'),
        }
    
    def getNormalAccts(self, cr, uid, ids, context=None):
        for sub in self.browse(cr, uid, ids, context=None):
            for line in sub.line_ids:
                if line.analytic_bool:
                    analyticReader = self.pool.get('account.analytic.account').read(cr, uid, line.analytic_id.id, ['normal_account'])
                    self.pool.get('recur.secondary.curr.line').write(cr, uid, line.id, {'account_id':analyticReader['normal_account'][0]})
                elif not line.analytic_bool:
                    continue
        return True
    def compute(self, cr, uid, ids, context=None):
        self.getNormalAccts(cr, uid, ids, context)
        for sub in self.browse(cr, uid, ids, context=context):
            if not sub.line_ids:
                raise osv.except_osv(_('Error!'), _('No entries has been set!'))
            elif sub.line_ids:
                allDebit = False
                allCredit = False
                for line in sub.line_ids:
                    allDebit+=line.debit
                    allCredit+=line.credit
                if allDebit==allCredit:
                    self.write(cr, uid, ids, {'state':'running'})
                elif allDebit!=allCredit:
                    raise osv.except_osv(_('Error!'), _('You can not activate unbalanced entries!'))
        return True
    
    def remove_line(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'draft'})
        return False
rsc()

class generate(osv.osv_memory):
    _name = 'recur.secondary.curr.generate'
    _description = "Generate Recurring Entries"
    _columns = {
        'date':fields.date('Effective Date'),
        'period':fields.many2one('account.period','Effective Period'),
        }
    _defaults = {
            'date': lambda *a: time.strftime('%Y-%m-%d'),
            }
generate()