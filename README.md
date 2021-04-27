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

Setup dependencies

```
make setup_deps
```

Configure global settings

```
make setup_global
```

Run relayer nodes

```
make setup_relayer
```

Run validator nodes

```
make setup_validator
```

Update relayer nodes

```
make update_relayer
```

Update validator nodes

```
make update_validator
```
