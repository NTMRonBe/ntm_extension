import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class bank_transfer(osv.osv):
    
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    
    _name = 'bank.transfer'
    _description = 'Bank Transfer'
    _columns = {
        'name':fields.char('Transfer ID',size=64),
        'date':fields.date('Transfer Date'),
        'handler':fields.many2one('res.users','Handler'),
        'journal_id':fields.many2one('account.journal','Bank Journal'),
        'period_id':fields.many2one('account.period','Transfer Period'),
        'ref':fields.char('Reference',size=64),
        'state':fields.selection([
                            ('draft','Draft'),
                            ('confirm','Confirm'),
                            ('done','Transferred'),
                            ],'State'),
        }
    _defaults = {
            'state':'draft',
            'period_id':_get_period,
            }
bank_transfer()

class bank_transfer_line(osv.osv):
    _name = 'bank.transfer.line'
    _description = 'Bank Transfer Lines'
    _columns = {
        'transfer_id':fields.many2one('bank.transfer','Transfer ID',ondelete='cascade'),
        'partner_id':fields.many2one('res.partner','Partner'),
        'account_number':fields.many2one('res.partner.bank','Bank Account'),
        'analytic_id':fields.many2one('account.analytic.account','Account'),
        }

    def on_change_act1(self, cr, uid, ids, bank_account1_id=False):
        result = {}
        currency_id=0
        if bank_account1_id:
            account = self.pool.get('account.account').browse(cr, uid, bank_account1_id)
            if account.currency_id:
                currency_id = account.currency_id.id
            elif not account.currency_id:
                currency_id = account.company_currency_id.id
            result = {'value':{
                    'currency_one':currency_id,
                      }
                }
        return result

    def onchange_partner(self, cr, uid, ids, partner_id=False):
        result = {}
        ctr = 0
        bank_account = False
        acc_account = False
        if partner_id:
            partner_read = self.pool.get('res.partner').read(cr, uid, partner_id,['name'])
            partner_name = partner_read['name']
            bank_ids = self.pool.get('res.partner.bank').search(cr, uid, [('partner_id','=',partner_id)])
            if not bank_ids:
                raise osv.except_osv(_('Error !'), _('%s has no bank account defined. Please define one.')%partner_name)
            elif bank_ids:
                for bank_id in bank_ids:
                    ctr += 1
                    bank_account = bank_id
                if ctr > 1:
                    raise osv.except_osv(_('Error !'), _('%s has %s bank accounts defined. Multiple bank accounts are not allowed')%(partner_name,ctr))
                elif ctr==1:
                    bank_account = bank_account
            acc_ids = self.pool.get('account.analytic.account').search(cr, uid, [('partner_id','=',partner_id)])
            if not acc_ids:
                raise osv.except_osv(_('Error !'), _('%s has no analytic account defined. Please define one.')%partner_name)
            elif acc_ids:
                acc_ctr = 0
                for acc_id in acc_ids:
                    acc_ctr += 1
                    acc_account = acc_id
                if acc_ctr > 1:
                    raise osv.except_osv(_('Error !'), _('%s has %s bank accounts defined. Multiple bank accounts are not allowed')%(partner_name, ctr))
                elif ctr==1:
                    acc_account = acc_account
            result = {'value':{
                    'account_number':bank_account,
                    'analytic_id':acc_account,
                    }
                }
        elif not partner_id:
            result = {'value':{
                    'account_number':False,
                    'analytic_id':False,
                    }
                }
        return result
bank_transfer_line()

class bt(osv.osv):
    _inherit = 'bank.transfer'
    _columns = {
        'line_ids':fields.one2many('bank.transfer.line','transfer_id','Transfer Lines'),
        }
    #def confirm(self, cr, uid, ids, context=None):
    #    for bt in self.read(cr, uid, ids, context=None):
            
            
bt()

class res_partner_bank(osv.osv):
    _inherit = 'res.partner.bank'
    _columns = {
        'partner_id': fields.many2one('res.partner', 'Partner', ondelete='cascade', select=True),
        'bank': fields.many2one('res.bank', 'Bank'),
        'ownership':fields.selection([
                                 ('company','Company Account'),
                                 ('entity','Entity Account')
                                 ],'Type'),
        }
res_partner_bank()
#class 