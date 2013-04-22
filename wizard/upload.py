import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp


class upload_invoice_slips(osv.osv):
    _name="invoice.slip.upload.wizard"
    _description="Upload Wizard"
    
    def upload_entries(self, cr, uid, ids, context=None):
        is_pool=self.pool.get('invoice.slip')
        isl_pool=self.pool.get('invoice.slip.line')
        isu_pool = self.pool.get('invoice.slip.upload')
        partner_list = []
        for rec in isu_pool.search(cr, uid, [('imported','=',False)]):
            rec_reader = isu_pool.read(cr, uid, rec, context=None)
            partner_name = rec_reader['partner_id']
            partner_id = False
            expense_id = False
            region_id=False
            region_code = rec_reader['region_id']
            expense_code = rec_reader['expense_code']
            trans_id = rec_reader['transaction_id']
            check_entity = self.pool.get('res.partner').search(cr, uid, [('name','ilike',partner_name)])
            check_region = self.pool.get('regional.configuration').search(cr, uid, [('code','ilike',region_code)])
            check_is = is_pool.search(cr, uid, [('transaction_id','=',trans_id)])
            if not check_entity:
                partner_list.append(partner_name)
                raise osv.except_osv(_('Error !'), _('%s is not yet included to our entity lists!')%partner_name)
            if check_entity:
                for entities in check_entity:
                    partner_id=entities 
            if not check_region:
                raise osv.except_osv(_('Error !'), _('%s is not yet included to our region lists!')%region_code)
            if check_region:
                region_ctr = 0
                for regions in check_region:
                    region_ctr+=1
                    region_id = regions
                if region_ctr >1:
                    raise osv.except_osv(_('Error !'), _('You have multiple regions with the same code! Kindly fix this before proceeding'))
                elif region_ctr==1:
                    check_expense = self.pool.get('regional.expenses').search(cr, uid, [('code','=',expense_code)])
                    if not check_expense:
                        raise osv.except_osv(_('Error !'), _('%s is not yet included to our expense lists!')%expense_code)
                    elif check_expense:
                        expense_ctr = 0
                        for expenses in check_expense:
                            expense_ctr+=1
                            expense_id = expenses
                        if expense_ctr > 1:
                            raise osv.except_osv(_('Error !'), _('You have multiple expenses with the same code! Kindly fix this before proceeding'))
                    check_expense_region = self.pool.get('regional.configuration.expenses').search(cr, uid, [('expense_id','=',expense_id),('regional_config_id','=',region_id)])
                    if not check_expense_region:
                        raise osv.except_osv(_('Error !'), _('%s is not included as an expense for the region %s!')%(expense_code,region_code))
            if not check_is:
                vals = {
                'transaction_id':trans_id,
                'transaction_type':rec_reader['transaction_type'],
                'region_id':region_id,
                'trans_date':rec_reader['trans_date'],
                'partner_id':partner_id,
                }
                inv_id = is_pool.create(cr, uid, vals)
                vals2 = {
                    'expense_id':expense_id,
                    'amount':rec_reader['amount'],
                    'comment':rec_reader['comment'],
                    'slip_id':inv_id,
                    }
                isl_pool.create(cr, uid, vals2)
            elif check_is:
                for inv in check_is:
                    vals2 = {
                    'expense_id':expense_id,
                    'amount':rec_reader['amount'],
                    'comment':rec_reader['comment'],
                    'slip_id':inv,
                    }
                    isl_pool.create(cr, uid, vals2)
        netsvc.Logger().notifyChannel("partner_list", netsvc.LOG_INFO, ' '+str(partner_list))
        return True
upload_invoice_slips()