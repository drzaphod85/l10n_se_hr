# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
import logging

_logger = logging.getLogger(__name__)

# This module extends the hr.leave.type model to include Swedish-specific vacation rules.
# It adds fields to manage vacation pay percentage and other Swedish-specific leave types.
# This is useful for companies operating in Sweden or having Swedish employees.
# This module is part of the Odoo Swedish Localization module, which provides
# localization features for Swedish companies, including tax calculations, payroll,
# and leave management.
# This module is designed to be used in conjunction with other modules in the
# Odoo Swedish Localization package. It is not intended to be used as a standalone module.
# It is important to note that this module may require additional configuration
# and customization to fully meet the needs of a specific company or organization.

_logger.debug("START processing file: hr_leave_type_inherit.py")

class HrLeaveTypeInherit(models.Model):
    _inherit = "hr.leave.type"

    # Collect all Swedish-specific leave types here
    # This allows for easy filtering and management of these leave types
    # in the Odoo interface, making it easier for HR managers to handle
    # different types of leave according to Swedish regulations.
    # This is a good practice to keep the code organized and maintainable.
    # It also helps in ensuring that the leave types are clearly defined
    # and can be easily referenced in other parts of the codebase.


    is_swedish_vacation = fields.Boolean(
        string='Swedish Vacation Rules Applicable',
        help="Indicates if specific Swedish vacation rules (Semesterlagen) apply to this time off type."
        defaulkt=False
    )

    _logger.info("... defined is_swedish_vacation")

    is_swedish_sick_leave = fields.Boolean(
        string='Swedish Sick Leave Rules Applicable',
        help="Indicates if specific Swedish sick leave rules (Sjuklönelagen) apply."
        default=False
    ) 
    _logger.info("... defined is_swedish_sick_leave") # Log after field definition

    
    is_swedish_parental_leave = fields.Boolean(
        string='Swedish Parental Leave Rules Applicable'
        help="Indicates if specific Swedish parental leave rules (Föräldraledighetslagen) apply."
        default=False
    )
    _logger.info("... defined is_swedish_parental_leave") # Log after field definition

    is_swedish_overtime = fields.Boolean(
        string='Swedish Overtime Rules Applicable',
        help="Indicates if specific Swedish overtime rules apply."
        default=False
    )
    _logger.info("... defined is_swedish_overtime") # Log after field definition

    # Fält specifikt för semester (från hr_vacation_leave_inherit.py)
    vacation_pay_percentage = fields.Float(
        string='Vacation Pay (%)',
        default=12.0,
        help='Default is 12%, can be higher based on collective agreements'
    )