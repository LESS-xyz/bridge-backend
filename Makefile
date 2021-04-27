
install_deps:
	ansible-playbook -i=ansible/hosts.yml ansible/tasks/install-deps.yml

setup_global:
	ansible-playbook -i=ansible/hosts.yml ansible/tasks/setup-global.yml


setup_relayer:
	ansible-playbook -i=ansible/hosts.yml ansible/tasks/setup-relayer.yml

setup_validator:
	ansible-playbook -i=ansible/hosts.yml ansible/tasks/setup-validator.yml


update_relayer:	setup_global setup_relayer

update_validator: setup_global setup_validator