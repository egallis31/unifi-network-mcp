# UniFi Controller API Endpoints

This document lists all UniFi Controller API endpoints used by the UniFi Network MCP server.

## Endpoints by Manager


### client_manager

- `POST` `/cmd/stamgr`
- `GET` `/rest/user`
- `GET` `/stat/sta`

### device_manager

- `POST` `/cmd/devmgr`

### firewall_manager

- `GET` `/firewall-policies`
- `POST` `/firewall-policies`
- `PUT` `/firewall-policies/batch`
- `GET` `/firewall/zones`
- `GET` `/ip-groups`
- `GET` `/rest/portforward`
- `POST` `/rest/portforward`
- `GET` `/trafficroutes`

### network_manager

- `GET` `/rest/networkconf`
- `POST` `/rest/networkconf`
- `GET` `/rest/wlanconf`
- `POST` `/rest/wlanconf`

### qos_manager

- `GET` `/qos-rules`
- `POST` `/qos-rules`

### system_manager

- `GET` `/api/self/sites`
- `GET` `/api/stat/admin`
- `POST` `/cmd/backup`
- `POST` `/cmd/sitemgr`
- `POST` `/cmd/system`
- `GET` `/stat/health`
- `GET` `/stat/status`
- `GET` `/stat/sysinfo`

### vpn_manager

- `GET` `/rest/networkconf`
- `POST` `/rest/vpnprofile`

## Endpoints by Category


### COMMANDS

- `POST` `/cmd/backup`
- `POST` `/cmd/devmgr`
- `POST` `/cmd/sitemgr`
- `POST` `/cmd/stamgr`
- `POST` `/cmd/system`

### NETWORKCONF

- `GET` `/rest/networkconf`
- `POST` `/rest/networkconf`

### OTHER

- `GET` `/api/self/sites`
- `GET` `/api/stat/admin`
- `GET` `/firewall-policies`
- `POST` `/firewall-policies`
- `PUT` `/firewall-policies/batch`
- `GET` `/firewall/zones`
- `GET` `/ip-groups`
- `GET` `/qos-rules`
- `POST` `/qos-rules`
- `GET` `/trafficroutes`

### PORTFORWARD

- `GET` `/rest/portforward`
- `POST` `/rest/portforward`

### STATISTICS

- `GET` `/stat/health`
- `GET` `/stat/sta`
- `GET` `/stat/status`
- `GET` `/stat/sysinfo`

### USER

- `GET` `/rest/user`

### VPNPROFILE

- `POST` `/rest/vpnprofile`

### WLANCONF

- `GET` `/rest/wlanconf`
- `POST` `/rest/wlanconf`

## Summary

- Total unique API endpoints: 27
- Total managers using APIs: 7
- API categories: 8

### HTTP Methods

- GET: 17
- POST: 23
- PUT: 1
