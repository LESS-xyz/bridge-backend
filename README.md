## Multisig Bridge


### Deployment

For deployment, you need to install Ansible

https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html#installing-ansible-on-specific-operating-systems

Also, for correct managing of docker-compose files of project, you need to install Posix Collection for Ansible

```
ansible-galaxy collection install ansible.posix
```

---

#### Configuration files

For configuration of deployment, copy files with example prefixes:

`hosts.example.yml` -> `hosts.yml`

`ansible/vars/environment.example.yml` -> `ansible/vars/environment.yml`

`ansible/vars/config-global.example.yml` -> `ansible/vars/config-global.yml`

And modify accordingly:

`hosts.yml` - This file used to specify servers and private keys

`ansible/vars/environment.yml`- This file used to deploy initial configurations to servers

`ansible/vars/config-global.yml` - This files used for configuring running Python applications

---

#### Deploying commands

### Initial configuration

Setup dependencies

```
make setup_deps
```

Configure global settings

```
make setup_global
```

---

### Setup node and run it

Configure and run relayer nodes

```
make setup_relayer
```

Configure and run validator nodes

```
make setup_validator
```

Configure and run bot nodes

```
make setup_bot
```

Configure and run all nodes

```
make setup_all
```

---

### Update node and restart it

Update and restart relayer nodes

```
make update_relayer
```

Update and restart validator nodes

```
make update_validator
```

Update and restart bot nodes

```
make update_bot
```

Update and restart all nodes

```
make update_all
```
