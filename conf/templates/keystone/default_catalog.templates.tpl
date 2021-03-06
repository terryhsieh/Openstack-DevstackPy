# From devstack commit 5f9473e8b9bdc15f42db597d5d1e766b760f764e with no modifications

# config for TemplatedCatalog, using camelCase because I don't want to do
# translations for legacy compat
catalog.RegionOne.identity.publicURL = http://%SERVICE_HOST%:$(public_port)s/v2.0
catalog.RegionOne.identity.adminURL = http://%SERVICE_HOST%:$(admin_port)s/v2.0
catalog.RegionOne.identity.internalURL = http://%SERVICE_HOST%:$(public_port)s/v2.0
catalog.RegionOne.identity.name = 'Identity Service'


catalog.RegionOne.compute.publicURL = http://%SERVICE_HOST%:8774/v2/$(tenant_id)s
catalog.RegionOne.compute.adminURL = http://%SERVICE_HOST%:8774/v2/$(tenant_id)s
catalog.RegionOne.compute.internalURL = http://%SERVICE_HOST%:8774/v2/$(tenant_id)s
catalog.RegionOne.compute.name = 'Compute Service'


catalog.RegionOne.volume.publicURL = http://%SERVICE_HOST%:8776/v1/$(tenant_id)s
catalog.RegionOne.volume.adminURL = http://%SERVICE_HOST%:8776/v1/$(tenant_id)s
catalog.RegionOne.volume.internalURL = http://%SERVICE_HOST%:8776/v1/$(tenant_id)s
catalog.RegionOne.volume.name = 'Volume Service'


catalog.RegionOne.ec2.publicURL = http://%SERVICE_HOST%:8773/services/Cloud
catalog.RegionOne.ec2.adminURL = http://%SERVICE_HOST%:8773/services/Admin
catalog.RegionOne.ec2.internalURL = http://%SERVICE_HOST%:8773/services/Cloud
catalog.RegionOne.ec2.name = 'EC2 Service'


catalog.RegionOne.image.publicURL = http://%SERVICE_HOST%:9292/v1
catalog.RegionOne.image.adminURL = http://%SERVICE_HOST%:9292/v1
catalog.RegionOne.image.internalURL = http://%SERVICE_HOST%:9292/v1
catalog.RegionOne.image.name = 'Image Service'

# More might be added in (in code)
