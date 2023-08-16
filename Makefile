do:
	docker run -d -v /var/run/docker.sock:/var/run/docker.sock -v /etc/nginx:/etc/nginx -v ./:/app -p 5000:8000 fastapillm