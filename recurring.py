import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
from datetime import datetime
from dateutil.relativedelta import relativedelta

class analytic_recur_entry(osv.osv):
    _name = 'analytic.recur.entry'
    _description = "Secondary Currency Recurring Entries"
    _columns = {
        'name':fields.char('Name', size=64, required=True),
        'journal_id':fields.many2one('account.journal','Journal', required=True),
        'currency_id':fields.many2one('res.currency', 'Currency', required=True),
        'state': fields.selection([('draft','Draft'),('running','Running'),('done','Done')], 'State', required=True, readonly=True),
        }
    
    _defaults = {
        'state':'draft'
    }
analytic_recur_entry()

class analytic_recur_entry_line(osv.osv):
    _name = 'analytic.recur.entry.line'
    _description = "Recurring Lines"
    _columns = {
        'name':fields.char('Description',size=64, required=True),
        'analytic_id':fields.many2one('account.analytic.account','Analytic Account'),
        'recur_id':fields.many2one('analytic.recur.entry','Recurring ID'),
        'debit':fields.float('Debit'),
        'credit':fields.float('Credit'),
        }
analytic_recur_entry_line()

class analytic_recur_entry_sched(osv.osv):
    _name = "analytic.recur.entry.sched"
    _description = "Schedule"
    _columns = {
        'recur_id': fields.many2one('analytic.recur.entry', 'Recurring ID', required=True, select=True, ondelete='cascade'),
        'date': fields.date('Date', required=True),
        'move_id': fields.many2one('account.move', 'Entry', ondelete='cascade'),
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
analytic_recur_entry_sched()

class rsc(osv.osv):
    _inherit = 'analytic.recur.entry'
    _columns = {
        'line_ids':fields.one2many('analytic.recur.entry.line','recur_id', 'Entry Lines'),
        'sched_ids':fields.one2many('analytic.recur.entry.sched','recur_id', 'Schedule'),
        }
    
    def compute(self, cr, uid, ids, context=None):
        for sub in self.browse(cr, uid, ids, context=context):
            if not sub.line_ids:
                raise osv.except_osv(_('Error!'), _('ARE-001: No entries has been set!'))
            elif sub.line_ids:
                allDebit = False
                allCredit = False
                for line in sub.line_ids:
                    allDebit+=line.debit
                    allCredit+=line.credit
                if allDebit==allCredit:
                    self.write(cr, uid, ids, {'state':'running'})
                elif allDebit!=allCredit:
                    raise osv.except_osv(_('Error!'), _('ARE-002: You can not activate unbalanced entries!'))
        return True
    
    def remove_line(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'draft'})
        return False
rsc()

class generate(osv.osv_memory):
    
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    
    _name = 'analytic.recur.entry.generate'
    _description = "Generate Recurring Entries"
    _columns = {
        'date':fields.date('Effective Date'),
        'period':fields.many2one('account.period','Effective Period'),
        }
    _defaults = {
            'date': lambda *a: time.strftime('%Y-%m-%d'),
            'period':_get_period,
            }
    
    def generateEntries(self, cr, uid, ids, context=None):
        user_id = uid
        user_read = self.pool.get('res.users').read(cr, uid, user_id, ['company_id'])
        company_read = self.pool.get('res.company').read(cr, uid, user_read['company_id'][0],['currency_id'])
        comp_curr = company_read['currency_id'][0]
        rate = False
        currency = False
        for form in self.read(cr, uid, ids, context=None):
            date = form['date']
            period_id = form['period']
            searchRecurring = self.pool.get('analytic.recur.entry').search(cr, uid, [('state','=','running')])
            for eachRecurring in searchRecurring:
                readRecur = self.pool.get('analytic.recur.entry').read(cr, uid, eachRecurring, context=None)
                journal_id = readRecur['journal_id'][0]
                name = readRecur['name']
                move = {
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'date':date,
                    'ref':name,
                }
                move_id = self.pool.get('account.move').create(cr, uid, move)
                recurCurr = readRecur['currency_id'][0]
                if recurCurr!=comp_curr:
                    curr_read = self.pool.get('res.currency').read(cr, uid, recurCurr,['rate'])
                    currency = recurCurr
                    rate = curr_read['rate']
                elif recurCurr==comp_curr:
                    currency= recurCurr
                    rate = 1.00
                for entry in readRecur['line_ids']:
                    lineRead = self.pool.get('analytic.recur.entry.line').read(cr, uid, entry, context=None)
                    analytic_read = self.pool.get('account.analytic.account').read(cr, uid, lineRead['analytic_id'][0],['normal_account'])
                    amount = False
                    amnt_curr = False
                    debit = False
                    credit = False
                    if lineRead['debit']>0.00:
                        amount = lineRead['debit'] / rate
                        amnt_curr = lineRead['debit']
                        debit = 0.00
                        credit = amount
                    elif lineRead['credit']>0.00:
                        amount = lineRead['credit'] / rate
                        amnt_curr = lineRead['credit']
                        debit = amount
                        credit = 0.00
                    move_line = {
                        'name':lineRead['name'],
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':analytic_read['normal_account'][0],
                        'debit':debit,
                        'credit':credit,
                        'date':date,
                        'ref':name,
                        'move_id':move_id,
                        'analytic_account_id':lineRead['analytic_id'][0],
                        'amount_currency':amnt_curr,
                        'currency_id':currency,
                        }
                    self.pool.get('account.move.line').create(cr, uid, move_line)
                self.pool.get('account.move').post(cr, uid, [move_id])
                recur_entry = {
                        'recur_id':eachRecurring,
                        'date':date,
                        'move_id':move_id,
                        }
                self.pool.get('analytic.recur.entry.sched').create(cr, uid, recur_entry)
        return {'type': 'ir.actions.act_window_close'}
generate()


class account_model(osv.osv):
    _inherit = "account.model"

    def generate(self, cr, uid, ids, datas={}, context=None):
        move_ids = []
        entry = {}
        account_move_obj = self.pool.get('account.move')
        account_move_line_obj = self.pool.get('account.move.line')
        pt_obj = self.pool.get('account.payment.term')
        
        pool = self.pool.get
        user_read = pool('res.users').read(cr, uid, uid, ['company_id'])
        company_read = pool('res.company').read(cr, uid, user_read['company_id'][0],['currency_id'])
        comp_curr = company_read['currency_id'][0]

        if context is None:
            context = {}

        if datas.get('date', False):
            context.update({'date': datas['date']})

        period_id = self.pool.get('account.period').find(cr, uid, dt=context.get('date', False))
        if not period_id:
            raise osv.except_osv(_('No period found !'), _('Unable to find a valid period !'))
        period_id = period_id[0]

        for model in self.browse(cr, uid, ids, context=context):
            entry['name'] = model.name%{'year':time.strftime('%Y'), 'month':time.strftime('%m'), 'date':time.strftime('%Y-%m')}
            move_id = account_move_obj.create(cr, uid, {
                'ref': entry['name'],
                'period_id': period_id,
                'journal_id': model.journal_id.id,
                'date': context.get('date',time.strftime('%Y-%m-%d'))
            })
            move_ids.append(move_id)
            for line in model.lines_id:
                analytic_account_id = False
                if line.analytic_account_id:
                    if not model.journal_id.analytic_journal_id:
                        raise osv.except_osv(_('No Analytic Journal !'),_("You have to define an analytic journal on the '%s' journal!") % (model.journal_id.name,))
                    analytic_account_id = line.analytic_account_id.id
                val = {
                    'move_id': move_id,
                    'journal_id': model.journal_id.id,
                    'period_id': period_id,
                    'analytic_account_id': analytic_account_id
                }

                date_maturity = time.strftime('%Y-%m-%d')
                if line.date_maturity == 'partner':
                    if not line.partner_id:
                        raise osv.except_osv(_('Error !'), _("Maturity date of entry line generated by model line '%s' of model '%s' is based on partner payment term!" \
                                                                "\nPlease define partner on it!")%(line.name, model.name))
                    if line.partner_id.property_payment_term:
                        payment_term_id = line.partner_id.property_payment_term.id
                        pterm_list = pt_obj.compute(cr, uid, payment_term_id, value=1, date_ref=date_maturity)
                        if pterm_list:
                            pterm_list = [l[0] for l in pterm_list]
                            pterm_list.sort()
                            date_maturity = pterm_list[-1]

                debit = credit = amount_curr = rate = 0.00
                
                line_currency = line.currency_id.id
                
                if line_currency != comp_curr:
                    curr_read = pool('res.currency').read(cr, uid, line_currency,['rate'])
                    rate = curr_read['rate']
    
                    if line.debit > 0.00:
                        amount = line.debit / rate
                        amount_curr = line.debit
                        debit = amount
                        credit = 0.00
                    elif line.credit > 0.00:
                        amount = line.credit / rate
                        amount_curr = line.credit
                        debit = 0.00
                        credit = amount
                else:    
                    if line.debit > 0.00:
                        debit = amount_curr = line.debit
                    elif line.credit > 0.00:
                        credit = amount_curr = line.credit
                

                val.update({
                    'name': line.name,
                    'quantity': line.quantity,
                    'debit': debit,
                    'credit': credit,
                    'amount_currency': amount_curr,
                    'currency_id': line_currency,
                    'account_id': line.account_id.id,
                    'move_id': move_id,
                    'partner_id': line.partner_id.id,
                    'date': context.get('date',time.strftime('%Y-%m-%d')),
                    'date_maturity': date_maturity
                })
                c = context.copy()
                c.update({'journal_id': model.journal_id.id,'period_id': period_id})
                account_move_line_obj.create(cr, uid, val, context=c)

        return move_ids

account_model()
