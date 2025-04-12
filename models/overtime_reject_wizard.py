from odoo import models, fields, api

class OvertimeRejectWizard(models.TransientModel):
    _name = 'overtime.reject.wizard'
    _description = 'Reject Overtime Wizard'
    
    overtime_id = fields.Many2one('hr.overtime.swedish', string='Overtime', required=True)
    rejection_reason = fields.Text(string='Rejection Reason', required=True)
    
    def action_reject(self):
        self.overtime_id.write({
            'state': 'rejected',
            'rejection_reason': self.rejection_reason
        })
        return {'type': 'ir.actions.act_window_close'}