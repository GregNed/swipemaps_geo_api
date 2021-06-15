update:
	git pull
	docker-compose pull
	docker-compose up -d
vacuum:
	docker rmi $(docker images -qf dangling=true) || true