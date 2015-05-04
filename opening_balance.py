import time
from osv import osv, fields, orm
import netsvc
import pooler
from tools.translate import _
import re

import calendar
import copy
import datetime
import logging
import warnings
import operator
import pickle
import re
import time
import traceback
import types

from lxml import etree
from tools.config import config

import tools
from tools.safe_eval import safe_eval as eval

class ob_import(osv.osv):
    _name = 'ob.import'
    _description = "Import Opening Balance Entries"
    _columns = {
        'name':fields.char('Name',size=64),
        'account_id':fields.many2one('account.account','Account'),
        'analytic_id':fields.many2one('account.analytic.account','Analytic Account'),
        'accpac_id':fields.char('Accpac Account',size=64),
        'debit':fields.float('Debit'),
        'credit':fields.float('Credit'),
        'currency_id':fields.many2one('res.currency','Posting Currency'),
        }
    
    def import_data(self, cr, uid, fields, datas, mode='init', current_module='', noupdate=False, context=None, filename=None):
        
        if not context:
            context = {}
        def _replace_field(x):
            x = re.sub('([a-z0-9A-Z_])\\.id$', '\\1/.id', x)
            return x.replace(':id','/id').split('/')
        fields = map(_replace_field, fields)
        logger = netsvc.Logger()
        ir_model_data_obj = self.pool.get('ir.model.data')

        # mode: id (XML id) or .id (database id) or False for name_get
        def _get_id(model_name, id, current_module=False, mode='id'):
            if mode=='.id':
                id = int(id)
                obj_model = self.pool.get(model_name)
                dom = [('id', '=', id)]
                if obj_model._columns.get('active'):
                    dom.append(('active', 'in', ['True','False']))
                ids = obj_model.search(cr, uid, dom, context=context)
                if not len(ids):
                    raise Exception(_("Database ID doesn't exist: %s : %s") %(model_name, id))
            elif mode=='id':
                if '.' in id:
                    module, xml_id = id.rsplit('.', 1)
                else:
                    module, xml_id = current_module, id
                record_id = ir_model_data_obj._get_id(cr, uid, module, xml_id)
                ir_model_data = ir_model_data_obj.read(cr, uid, [record_id], ['res_id'], context=context)
                if not ir_model_data:
                    raise ValueError('No references to %s.%s' % (module, xml_id))
                id = ir_model_data[0]['res_id']
            else:
                obj_model = self.pool.get(model_name)
                ids = obj_model.name_search(cr, uid, id, operator='ilike', context=context)
                if not ids:
                    raise ValueError('No record found for %s' % (id,))
                id = ids[0][0]
            return id

        def process_liness(self, datas, prefix, current_module, model_name, fields_def, position=0, skip=0):
            line = datas[position]
            row = {}
            warning = []
            data_res_id = False
            xml_id = False
            nbrmax = position+1

            done = {}
            for i in range(len(fields)):
                res = False
                if i >= len(line):
                    raise Exception(_('Please check that all your lines have %d columns.') % (len(fields),))

                field = fields[i]
                if field[:len(prefix)] <> prefix:
                    if line[i] and skip:
                        return False
                    continue

                # ID of the record using a XML ID
                if field[len(prefix)]=='id':
                    try:
                        data_res_id = _get_id(model_name, line[i], current_module, 'id')
                    except ValueError, e:
                        pass
                    xml_id = line[i]
                    continue

                # ID of the record using a database ID
                elif field[len(prefix)]=='.id':
                    data_res_id = _get_id(model_name, line[i], current_module, '.id')
                    continue

                # recursive call for getting children and returning [(0,0,{})] or [(1,ID,{})]
                if fields_def[field[len(prefix)]]['type']=='one2many':
                    if field[len(prefix)] in done:
                        continue
                    done[field[len(prefix)]] = True
                    relation_obj = self.pool.get(fields_def[field[len(prefix)]]['relation'])
                    newfd = relation_obj.fields_get(cr, uid, context=context)
                    pos = position
                    res = []
                    first = 0
                    while pos < len(datas):
                        res2 = process_liness(self, datas, prefix + [field[len(prefix)]], current_module, relation_obj._name, newfd, pos, first)
                        if not res2:
                            break
                        (newrow, pos, w2, data_res_id2, xml_id2) = res2
                        nbrmax = max(nbrmax, pos)
                        warning += w2
                        first += 1
                        if (not newrow) or not reduce(lambda x, y: x or y, newrow.values(), 0):
                            break
                        res.append( (data_res_id2 and 1 or 0, data_res_id2 or 0, newrow) )

                elif fields_def[field[len(prefix)]]['type']=='many2one':
                    relation = fields_def[field[len(prefix)]]['relation']
                    if len(field) == len(prefix)+1:
                        mode = False
                    else:
                        mode = field[len(prefix)+1]
                    res = line[i] and _get_id(relation, line[i], current_module, mode) or False

                elif fields_def[field[len(prefix)]]['type']=='many2many':
                    relation = fields_def[field[len(prefix)]]['relation']
                    if len(field) == len(prefix)+1:
                        mode = False
                    else:
                        mode = field[len(prefix)+1]

                    # TODO: improve this by using csv.csv_reader
                    res = []
                    if line[i]:
                        for db_id in line[i].split(config.get('csv_internal_sep')):
                            res.append( _get_id(relation, db_id, current_module, mode) )
                    res = [(6,0,res)]

                elif fields_def[field[len(prefix)]]['type'] == 'integer':
                    res = line[i] and int(line[i]) or 0
                elif fields_def[field[len(prefix)]]['type'] == 'boolean':
                    res = line[i].lower() not in ('0', 'false', 'off')
                elif fields_def[field[len(prefix)]]['type'] == 'float':
                    res = line[i] and float(line[i]) or 0.0
                elif fields_def[field[len(prefix)]]['type'] == 'selection':
                    for key, val in fields_def[field[len(prefix)]]['selection']:
                        if line[i] in [tools.ustr(key), tools.ustr(val)]:
                            res = key
                            break
                    if line[i] and not res:
                        logger.notifyChannel("import", netsvc.LOG_WARNING,
                                _("key '%s' not found in selection field '%s'") % \
                                        (line[i], field[len(prefix)]))
                        warning += [_("Key/value '%s' not found in selection field '%s'") % (line[i], field[len(prefix)])]
                else:
                    res = line[i]

                row[field[len(prefix)]] = res or False

            result = (row, nbrmax, warning, data_res_id, xml_id)
            return result

        fields_def = self.fields_get(cr, uid, context=context)

        if config.get('import_partial', False) and filename:
            data = pickle.load(file(config.get('import_partial')))
            original_value = data.get(filename, 0)

        position = 0
        while position<len(datas):
            res = {}

            (res, position, warning, res_id, xml_id) = \
                    process_liness(self, datas, [], current_module, self._name, fields_def, position=position)
            if len(warning):
                cr.rollback()
                return (-1, res, 'Line ' + str(position) +' : ' + '!\n'.join(warning), '')

            try:
                id = ir_model_data_obj._update(cr, uid, self._name,
                     current_module, res, mode=mode, xml_id=xml_id,
                     noupdate=noupdate, res_id=res_id, context=context)
            except Exception, e:
                return (-1, res, 'Line ' + str(position) +' : ' + tools.ustr(e), '')

            if config.get('import_partial', False) and filename and (not (position%100)):
                data = pickle.load(file(config.get('import_partial')))
                data[filename] = position
                pickle.dump(data, file(config.get('import_partial'), 'wb'))
                if context.get('defer_parent_store_computation'):
                    self._parent_store_compute(cr)
                cr.commit()

        if context.get('defer_parent_store_computation'):
            self._parent_store_compute(cr)
        return (position, 0, 0, 0)
ob_import()

class ob_import_wiz(osv.osv_memory):
    _name = 'ob.import.wiz'
    _columns = {
        'journal_id':fields.many2one('account.journal','Opening Balance Journal', domain=[('type','=','situation')],required=True),
        'period_id':fields.many2one('account.period','Effective Period',required=True),
        'date':fields.date('Effectivity Date',required=True),
        'name':fields.char('Reference',size=64, required=True),
    }
        
    def createEntries(self, cr, uid, ids, context=None):
        pool = self.pool.get
        for form in self.read(cr, uid, ids, context=None):
            move = {
                'ref':form['name'],
                'journal_id':form['journal_id'],
                'period_id':form['period_id'],
                'date':form['date'],
                'state':'draft',
                }
            move_id = pool('account.move').create(cr, uid, move)
            lines = pool('ob.import').read(cr, uid, context['active_ids'], context=None)
            for lineRead in lines:
                #lineRead = pool('ob.import').read(cr, uid, line, context=None)
                account_id = False
                curr_id = False
                analytic_id = False
                
                #print lineRead
                if lineRead['analytic_id']:
                    analytic_id = lineRead['analytic_id'][0]
                    analyticRead = pool('account.analytic.account').read(cr, uid, analytic_id, ['normal_account'])
                    account_id = analyticRead['normal_account'][0]
                elif lineRead['account_id']:
                    account_id = lineRead['account_id'][0]
                    analytic_id = False
                elif lineRead['accpac_id']:
                    checker = pool('account.accpac').search(cr, uid, [('name','=',lineRead['accpac_id']),('state','=','matched')], limit=1)
                    if checker:
                        checker_read = pool('account.accpac').read(cr, uid, checker[0],context=None)
                        if checker_read['account_id']:
                            account_id = checker_read['account_id'][0]
                        elif checker_read['analytic_id']:
                            analytic_id = checker_read['analytic_id'][0]
                            analyticReader = pool('account.analytic.account').read(cr, uid, analytic_id,['normal_account'])
                            account_id = analyticReader['normal_account'][0]
                    if not checker:
                        account_number = lineRead['accpac_id']
                        raise osv.except_osv(_('Error!'), _('Please use the Accpac Account Matcher and Wizard to add a link to %s account!')%(account_number))
                curr_id = lineRead['currency_id'][0]    
                move_line = {
                    'name':lineRead['name'],
                    'journal_id':form['journal_id'],
                    'period_id':form['period_id'],
                    'date':form['date'],
                    'account_id':account_id,
                    'currency_id':curr_id,
                    'analytic_account_id':analytic_id,
                    'debit':lineRead['debit'],
                    'credit':lineRead['credit'],
                    'move_id':move_id,
                }
                pool('account.move.line').create(cr, uid, move_line)
            pool('ob.import').unlink(cr, uid, context['active_ids'])
        #return {'type': 'ir.actions.act_window_close'}
        print "Done!"
        return True
ob_import_wiz()