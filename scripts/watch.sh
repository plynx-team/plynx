watchmedo auto-restart --recursive --pattern="*.py" --directory="/app/plynx" -- python -c 'import plynx.bin; plynx.bin.main()' $PLYNX_MODE -vvv
