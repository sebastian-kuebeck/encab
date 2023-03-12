.PHONY: dist build run

dist:
	cd ../.. && python -m build
	rm -r ../../src/encab.egg-info
	cp ../../dist/encab-*.whl .

build: dist
	docker build --build-arg ENCAB_WHEEL=`ls encab-*.whl` -t encab_minimum .
	rm encab-*.whl

run:
	docker run encab_minimum
