.PHONY: dist build run

dist:
	cd ../.. && make dist
	rm -rf ../../src/encab.egg-info
	cp ../../dist/encab-*.whl .

build: dist
	docker build --build-arg ENCAB_WHEEL=`ls encab-*.whl` -t encab_loadtest .
	rm -f encab-*.whl

run:
	docker run encab_loadtest
