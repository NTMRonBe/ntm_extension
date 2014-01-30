from osv import fields, osv
import netsvc

class res_users_set_location(osv.osv_memory):
	_name = "res.users.set.location"
	_columns = {
		'location':fields.char("File Location",size=100, required=True),
	}
	_defaults = {
		'location':'/home/username/',
	}
	def set_location(self,cr, uid, ids, context=None):
		users_pool = self.pool.get('res.users')
		for form in self.read(cr, uid, ids, context=context):
			for id in context['active_ids']:
				for user_id in users_pool.browse(cr, uid, [id]):
					user_uid = user_id.id
					loc = form['location']
					users_pool.write(cr, uid, user_uid, {'location':loc})
		return {'type': 'ir.actions.act_window_close'}
res_users_set_location()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: