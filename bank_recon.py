import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
from compiler.ast import Add

class bank_recon(osv.osv):
    _name = 'bank.recon'
    _description = "Bank Reconciliation"
    _columns = {
        'name':fields.char('Reconciliation #',size=64),
        'bank_id':fields.many2one('res.partner.bank','Bank'),
        'date':fields.date('Reconciliation Date'),
        'type':fields.selection([
                        ('check_clearing','Check Clearing'),
                        ('wire_transfer_clearing','Wire Transfer Clearing'),
                        ('fund_transfer_clearing','Fund Transfer Clearing'),
                        ]),
        'state':fields.selection([
                        ('draft','Draft'),
                        ('confirmed','Confirmed'),
                        ('reconciled','Reconciled'),
                        ],'State'),
        }
    _defaults = {
            'state':'draft',
            'date': lambda *a: time.strftime('%Y-%m-%d'),
            'name':'NEW',
            }
bank_recon()

class bank_recon_line(osv.osv):
    _name = 'bank.recon.line'
    _description = "Bank Reconciliation Line"
    _columns = {
        'recon_id':fields.many2one('bank.recon','Reconciliation ID'),
        'name':fields.char('Reference',size=100),
        'amount':fields.float('Amount'),
        'account_id':fields.many2one('account.account','Account'),
        'date':fields.date('Check Date'),
        'recon_date':fields.date('Actual Clearing Date'),
        'check_id':fields.many2one('res.partner.check.numbers','Check Number'),
        'move_line_id':fields.many2one('account.move.line','Move line'),
        }
bank_recon_line()

class bank_recon2(osv.osv):
    _inherit = 'bank.recon'
    _columns = {
        'line_ids':fields.one2many('bank.recon.line','recon_id','Reconciliation Lines'),
        'move_id':fields.many2one('account.move','Journal Entry'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'enabled':fields.boolean('Enabled'),
        }
    def create(self, cr, uid, vals, context=None):
        vals.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'bank.recon'),
        })
        return super(bank_recon, self).create(cr, uid, vals, context)
    
    def enabler(self, cr, uid, ids, context=None):
        for br in self.read(cr, uid, ids, context=None):
            self.write(cr, uid, ids, {'enabled':True})
        return True
    def onchange_bankid(self, cr, uid, ids, bank_id, date, context=None):
        result = {}
        line_ids = []
        if ids:
            if bank_id or date:
                for recon in self.read(cr, uid, ids, context=None):
                    if recon['type']=='check_clearing':
                        self.pool.get('bank.recon.line').unlink(cr, uid, recon['line_ids'])
                        check_search = self.pool.get('expense.check.payment').search(cr, uid, [('bank_account_id','=',bank_id),('check_date','<=',date),('state','=','posted')])
                        print check_search
                        for checks in check_search:
                            check_read = self.pool.get('expense.check.payment').read(cr, uid, checks,['check_number','amount2pay','check_date'])
                            check_state = self.pool.get('res.partner.check.numbers').read(cr, uid, check_read['check_number'][0],['state'])
                            if check_state['state']=='released':
                                line = {
                                    'name':check_read['check_number'][1],
                                    'amount':check_read['amount2pay'],
                                    'date':check_read['check_date'],
                                    'recon_id':recon['id'],
                                    'recon_date':date,
                                    'check_id':check_read['check_number'][0],
                                    }
                                check_num = check_read['check_number'][1]
                                print check_num
                                entry_search = self.pool.get('account.move.line').search(cr, uid, [('name','=',check_num)])
                                print entry_search
                                if entry_search:
                                    entry_read = self.pool.get('account.move.line').read(cr, uid, entry_search[0],['account_id'])
                                    line.update({'account_id':entry_read['account_id'][0],'move_line_id':entry_search[0]})
                                    line_id = self.pool.get('bank.recon.line').create(cr, uid, line)
                                    line_ids.append(line_id)
                    if recon['type']=='fund_transfer_clearing':
                        self.pool.get('bank.recon.line').unlink(cr, uid, recon['line_ids'])
                        bt_search = self.pool.get('bank.transfer').search(cr, uid, [('journal_id','=',bank_id),
                                                                                    ('date','<=',date),('state','=','done')])
                        print bt_search
                        print recon['type']
                        for bt in bt_search:
                            bt_read = self.pool.get('bank.transfer').read(cr, uid, bt, context=None)
                            line = {
                                'name':bt_read['name'],
                                'recon_date':date,
                                'recon_id':recon['id'],
                                'date':bt_read['date'],
                                'amount':bt_read['amount'],
                                }
                            line_id = self.pool.get('bank.recon.line').create(cr, uid, line)
                            line_ids.append(line_id)
                result = {'value':{'line_ids':line_ids}}
                return result
        if not ids:
            return result
        
    def reconcile(self, cr, uid, ids, context=None):
        for recon in self.read(cr, uid, ids, context=None):
            period_search = self.pool.get('account.period').search(cr, uid, [('date_start','<=',recon['date']),('date_stop','>=',recon['date'])],limit=1)
            bank_read = self.pool.get('res.partner.bank').read(cr, uid, recon['bank_id'][0],['journal_id','transit_id','account_id'])
            b1_curr = self.pool.get('account.account').read(cr, uid, bank_read['account_id'][0],['company_currency_id','currency_id'])
            journal_id = bank_read['journal_id'][0]
            rate = False
            currency = False
            if not b1_curr['currency_id']:
                currency = b1_curr['company_currency_id'][0]
                rate = 1.00
            elif b1_curr['currency_id']:
                curr_read = self.pool.get('res.currency').read(cr, uid, b1_curr['currency_id'][0],['rate'])
                currency = b1_curr['currency_id'][0]
                rate = curr_read['rate']
            period_id = period_search[0]
            move = {
                'period_id':period_search[0],
                'date':recon['date'],
                'journal_id':bank_read['journal_id'][0],
                'name':recon['name'],
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            #move_id=False
            print context
            if recon['type']=='check_clearing':
                rec_list_ids = []
                for line in recon['line_ids']:
                    line_read = self.pool.get('bank.recon.line').read(cr, uid, line,context=None)
                    credit = line_read['amount']/rate
                    move_line = {
                        'name':line_read['name'],
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':bank_read['account_id'][0],
                        'credit':credit,
                        'date':line_read['recon_date'],
                        'ref':line_read['name'],
                        'move_id':move_id,
                        'amount_currency':line_read['amount'],
                        'currency_id':currency,
                    }
                    self.pool.get('account.move.line').create(cr, uid, move_line)
                    move_line = {
                        'name':line_read['name'],
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':line_read['account_id'][0],
                        'debit':credit,
                        'date':line_read['recon_date'],
                        'ref':line_read['name'],
                        'move_id':move_id,
                        'amount_currency':line_read['amount'],
                        'currency_id':currency,
                    }
                    recon_move_line = self.pool.get('account.move.line').create(cr, uid, move_line)
                    rec_ids = [recon_move_line,line_read['move_line_id'][0]]
                    rec_list_ids.append(rec_ids)
                    self.pool.get('res.partner.check.numbers').write(cr, uid,line_read['check_id'][0],{'state':'cleared'})
                self.pool.get('account.move').post(cr, uid, [move_id])
                for rec_ids in rec_list_ids:
                    if len(rec_ids) >= 2:
                        self.pool.get('account.move.line').reconcile_partial(cr, uid, rec_ids)
                self.pool.get('bank.recon').write(cr, uid, ids,{'state':'reconciled','move_id':move_id} )
            elif recon['type']=='fund_transfer_clearing':
                rec_list_ids = []
                for line in recon['line_ids']:
                    line_read = self.pool.get('bank.recon.line').read(cr, uid, line,context=None)
                    credit = line_read['amount']/rate
                    name = "Transit account of transfer request # " + line_read['name']
                    move_line_vals = {
                        'name':name,
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':bank_read['transit_id'][0],
                        'debit':credit,
                        'date':line_read['recon_date'],
                        'move_id':move_id,
                        'amount_currency':line_read['amount'],
                        'currency_id':currency,
                    }
                    self.pool.get('account.move.line').create(cr, uid, move_line_vals)
                    credit = line_read['amount']/rate
                    name = "Withdraw from bank account #"+recon['bank_id'][1]+" for transfer request # " + line_read['name']
                    move_line_vals = {
                        'name':name,
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':bank_read['account_id'][0],
                        'credit':credit,
                        'date':line_read['recon_date'],
                        'move_id':move_id,
                        'amount_currency':line_read['amount'],
                        'currency_id':currency,
                    }
                    self.pool.get('account.move.line').create(cr, uid, move_line_vals)
                    move_lines = self.pool.get('account.move.line').search(cr, uid, [('ref','=',line_read['name']),
                                                                                     ('move_id.state','=','posted'),
                                                                                     ('analytic_account_id','!=',False)
                                                                                     ])
                    print move_lines
                    for move_line in move_lines:
                        move_line_read = self.pool.get('account.move.line').read(cr, uid, move_line,context=None)
                        print move_line_read
                        analytic_id = move_line_read['analytic_account_id'][0]
                        credit = move_line_read['amount_currency']/rate
                        name = "Clearing of transfer request # " + move_line_read['ref']
                        move_line_vals = {
                            'name':name,
                            'journal_id':journal_id,
                            'period_id':period_id,
                            'account_id':move_line_read['account_id'][0],
                            'debit':credit,
                            'analytic_account_id':analytic_id,
                            'date':line_read['recon_date'],
                            'move_id':move_id,
                            'amount_currency':move_line_read['amount_currency'],
                            'currency_id':currency,
                        }
                        self.pool.get('account.move.line').create(cr, uid, move_line_vals)
                        name = "Reversal of " + move_line_read['name']
                        move_line_vals = {
                            'name':name,
                            'journal_id':journal_id,
                            'period_id':period_id,
                            'account_id':move_line_read['account_id'][0],
                            'credit':credit,
                            'date':line_read['recon_date'],
                            'analytic_account_id':analytic_id,
                            'move_id':move_id,
                            'amount_currency':move_line_read['amount_currency'],
                            'currency_id':currency,
                        }
                        self.pool.get('account.move.line').create(cr, uid, move_line_vals)
                        bt_search = self.pool.get('bank.transfer').search(cr, uid, [('name','=',line_read['name'])])
                        self.pool.get('bank.transfer').write(cr, uid, bt_search,{'state':'transferred'})
                self.pool.get('account.move').post(cr, uid, [move_id])
                self.pool.get('bank.recon').write(cr, uid, ids,{'state':'reconciled','move_id':move_id} )
        return True
bank_recon2()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,