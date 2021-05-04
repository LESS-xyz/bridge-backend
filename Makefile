
setup_deps:
	ansible-playbook -i=ansible/hosts.yml ansible/tasks/global-install-deps.yml

setup_global:
	ansible-playbook -i=ansible/hosts.yml ansible/tasks/global-sync-configure.yml


setup_relayer:
	ansible-playbook -i=ansible/hosts.yml ansible/tasks/group_tasks/relayers.yml

setup_validator:
	ansible-playbook -i=ansible/hosts.yml ansible/tasks/group_tasks/validators.yml

setup_bot:
	ansible-playbook -i=ansible/hosts.yml ansible/tasks/group_tasks/bots.yml

setup_all:
	ansible-playbook -i=ansible/hosts.yml ansible/tasks/group_tasks/all.yml

update_relayer:	setup_global setup_relayer

update_validator: setup_global setup_validator

update_bot: setup_global setup_bot

update_all: setup_global setup_all
