# From devstack commit 30439a6dc4

[pipeline:glance-api]
#pipeline = versionnegotiation context apiv1app
# NOTE: use the following pipeline for keystone
pipeline = versionnegotiation authtoken auth-context apiv1app

# To enable Image Cache Management API replace pipeline with below:
# pipeline = versionnegotiation context imagecache apiv1app
# NOTE: use the following pipeline for keystone auth (with caching)
# pipeline = versionnegotiation authtoken auth-context imagecache apiv1app

[app:apiv1app]
paste.app_factory = glance.common.wsgi:app_factory
glance.app_factory = glance.api.v1.router:API

[filter:versionnegotiation]
paste.filter_factory = glance.common.wsgi:filter_factory
glance.filter_factory = glance.api.middleware.version_negotiation:VersionNegotiationFilter

[filter:cache]
paste.filter_factory = glance.common.wsgi:filter_factory
glance.filter_factory = glance.api.middleware.cache:CacheFilter

[filter:cachemanage]
paste.filter_factory = glance.common.wsgi:filter_factory
glance.filter_factory = glance.api.middleware.cache_manage:CacheManageFilter

[filter:context]
paste.filter_factory = glance.common.wsgi:filter_factory
glance.filter_factory = glance.common.context:ContextMiddleware

[filter:authtoken]
paste.filter_factory = keystone.middleware.auth_token:filter_factory
service_host = %KEYSTONE_SERVICE_HOST%
service_port = %KEYSTONE_SERVICE_PORT%
service_protocol = %KEYSTONE_SERVICE_PROTOCOL%
auth_host = %KEYSTONE_AUTH_HOST%
auth_port = %KEYSTONE_AUTH_PORT%
auth_protocol = %KEYSTONE_AUTH_PROTOCOL%
auth_uri = %KEYSTONE_SERVICE_PROTOCOL%://%KEYSTONE_SERVICE_HOST%:%KEYSTONE_SERVICE_PORT%/
admin_token = %SERVICE_TOKEN%

[filter:auth-context]
paste.filter_factory = glance.common.wsgi:filter_factory
glance.filter_factory = keystone.middleware.glance_auth_token:KeystoneContextMiddleware


