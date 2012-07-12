# -*- coding: utf-8 -*-

# Copyright © 2010-2011 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

"""
Utility functions to manage permissions and roles in pulp.
"""

from gettext import gettext as _

from pulp.server.api.permission import PermissionAPI
from pulp.server.api.role import RoleAPI
from pulp.server.auth.principal import (
    get_principal, is_system_principal, SystemPrincipal)
from pulp.server.exceptions import PulpException

#from pulp.server.managers import factory

_permission_api = PermissionAPI()
_role_api = RoleAPI()


class PulpAuthorizationError(PulpException):
    pass

# operations api --------------------------------------------------------------

CREATE, READ, UPDATE, DELETE, EXECUTE = range(5)
operation_names = ['CREATE', 'READ', 'UPDATE', 'DELETE', 'EXECUTE']


# Temporarily moved this out of db into here; this is the only place using it
# and it's going to be deleted.

def name_to_operation(name):
    """
    Convert a operation name to an operation value
    Returns None if the name does not correspond to an operation
    @type name: str
    @param name: operation name
    @rtype: int or None
    @return: operation value
    """
    name = name.upper()
    if name not in operation_names:
        return None
    return operation_names.index(name)


def names_to_operations(names):
    """
    Convert a list of operation names to operation values
    Returns None if there is any name that does not correspond to an operation
    @type name: list or tuple of str's
    @param names: names to convert to values
    @rtype: list of int's or None
    @return: list of operation values
    """
    operations = [name_to_operation(n) for n in names]
    if None in operations:
        return None
    return operations


def operation_to_name(operation):
    """
    Convert an operation value to an operation name
    Returns None if the operation value is invalid
    @type operation: int
    @param operation: operation value
    @rtype: str or None
    @return: operation name
    """
    if operation < CREATE or operation > EXECUTE:
        return None
    return operation_names[operation]

# utilities -------------------------------------------------------------------


def _get_operations(operation_names):
    """
    Get a list of operation values give a list of operation names
    Raise an exception if any of the names are invalid
    @type operation_names: list or tuple of str's
    @param operation_names: list of operation names
    @rtype: list of int's
    @return: list of operation values
    @raise L{PulpAuthorizationError}: on any invalid names
    """
    operations = names_to_operations(operation_names)
    if operations is None:
        raise PulpAuthorizationError(_('invalid operation name or names: %s') %
                            ', '.join(operation_names))
    return operations



def _operations_not_granted_by_roles(resource, operations, roles):
    """
    Filter a list of operations on a resource, removing the operations that
    are granted to the resource by any role in a given list of roles
    @type resource: str
    @param resource: pulp resource
    @type operations: list or tuple of int's
    @param operations: operations pertaining to the resource
    @type roles: list or tuple of L{pulp.server.db.model.Role} instances
    @param roles: list of roles
    @rtype: list of int's
    @return: list of operations on resource not granted by the roles
    """
    culled_ops = operations[:]
    for role in roles:
        permissions = role['permissions']
        if resource not in permissions:
            continue
        for operation in culled_ops[:]:
            if operation in permissions[resource]:
                culled_ops.remove(operation)
    return culled_ops

# permissions api -------------------------------------------------------------





def grant_automatic_permissions_to_consumer_user(user_name):
    """
    Grant the permissions required by a consumer user.
    @type user_name: str
    @param user_name: name of the consumer user
    @type user_resource: str
    @param user_resource: the resource path for the consumer user
    @rtype: bool
    @return: True on success, False otherwise
    """
    user = _get_user(user_name)
    user_operations = [READ, UPDATE, DELETE, EXECUTE]
    _permission_api.grant('/consumers/%s/' % user_name, user, user_operations)


class GrantPermissionsForTask(object):
    """
    Grant appropriate permissions to a task resource for the user that started
    the task.
    """

    def __init__(self):
        self.user_name = get_principal()['login']

    def __call__(self, task):
        if self.user_name == SystemPrincipal.LOGIN:
            return
        resource = '/tasks/%s/' % task.id
        operations = ['READ', 'DELETE']
        grant_permission_to_user(resource, self.user_name, operations)


class RevokePermissionsForTask(object):
    """
    Revoke the permissions for a task from the user that started the task.
    """

    def __init__(self):
        self.user_name = get_principal()['login']

    def __call__(self, task):
        if self.user_name == SystemPrincipal.LOGIN:
            return
        resource = '/tasks/%s/' % task.id
        operations = ['READ', 'DELETE']
        revoke_permission_from_user(resource, self.user_name, operations)


class GrantPermmissionsForTaskV2(GrantPermissionsForTask):

    def __call__(self, call_request, call_report):
        if self.user_name == SystemPrincipal.LOGIN:
            return
        resource = '/v2/tasks/%s/' % call_report.task_id
        operations = ['READ', 'DELETE']
        grant_permission_to_user(resource, self.user_name, operations)


class RevokePermissionsForTaskV2(RevokePermissionsForTask):

    def __call__(self, call_request, call_report):
        if self.user_name == SystemPrincipal.LOGIN:
            return
        resource = '/v2/tasks/%s/' % call_report.task_id
        operations = ['READ', 'DELETE']
        revoke_permission_from_user(resource, self.user_name, operations)

# role api --------------------------------------------------------------------

def create_role(role_name):
    """
    Create a role with the give name
    Raises and exception if the role already exists
    @type role_name: str
    @param role_name: name of role
    @rtype: bool
    @return: True on success
    """
    return _role_api.create(role_name)



def list_users_in_role(role_name):
    """
    Get a list of the users belonging to a role
    @type role_name: str
    @param role_name: name of role
    @rtype: list of L{pulp.server.db.model.User} instances
    @return: users belonging to the role
    """
    role = _get_role(role_name)
    return _get_users_belonging_to_role(role)

# built in roles --------------------------------------------------------------

super_user_role = 'super-users'
consumer_users_role = 'consumer-users'


def is_last_super_user(user):
    """
    Check to see if a user is the last super user
    @type user: L{pulp.server.db.model.User} instace
    @param user: user to check
    @rtype: bool
    @return: True if the user is the last super user, False otherwise
    @raise PulpException: if no super users are found
    """
    if super_user_role not in user['roles']:
        return False
    role = _role_api.role(super_user_role)
    users = _get_users_belonging_to_role(role)
    if not users:
        raise PulpException(_('no super users defined'))
    if len(users) >= 2:
        return False
    return users[0]['_id'] == user['_id'] # this should be True


def check_builtin_roles(role_name):
    """
    Check to see if a role name corresponds to a built in role, and raise an
    exception if it does
    @type role_name: str
    @param role_name: name of role to check
    @raise L{PulpAuthorizationError}: if the role name matches a built in role
    """
    if role_name not in (super_user_role, consumer_users_role):
        return
    raise PulpAuthorizationError(_('role %s cannot be changed') % role_name)


# authorization api -----------------------------------------------------------

def is_superuser(user):
    """
    Return True if the user is a super user
    @type user: L{pulp.server.db.model.User} instance
    @param user: user to check
    @rtype: bool
    @return: True if the user is a super user, False otherwise
    """
    return super_user_role in user['roles']


def is_authorized(resource, user, operation):
    """
    Check to see if a user is authorized to perform an operation on a resource
    @type resource: str
    @param resource: pulp resource path
    @type user: L{pulp.server.db.model.User} instance
    @param user: user to check permissions for
    @type operation: int
    @param operation: operation to be performed on resource
    @rtype: bool
    @return: True if the user is authorized for the operation on the resource,
             False otherwise
    """
    if is_superuser(user):
        return True
    login = user['login']
    parts = [p for p in resource.split('/') if p]
    while parts:
        current_resource = '/%s/' % '/'.join(parts)
        permission = _permission_api.permission(current_resource)
        if permission is not None:
            if operation in permission['users'].get(login, []):
                return True
        parts = parts[:-1]
    permission = _permission_api.permission('/')
    return (permission is not None and
            operation in permission['users'].get(login, []))
