.PHONY: dist build run

dist:
	rm -f encab-*.whl
	cd ../.. && python -m build
	rm -r ../../src/encab.egg-info
	cp ../../dist/encab-*.whl .

build: dist
	docker build --build-arg ENCAB_WHEEL=`ls encab-*.whl` -t encab_integration .
	rm encab-*.whl

test: build
	docker run encab_integration
