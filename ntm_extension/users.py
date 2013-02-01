from osv import fields, osv
import netsvc


class res_users(osv.osv):
	_inherit = "res.users"
	_columns = {
		'location':fields.char("File Location",size=100),
		}
res_users()