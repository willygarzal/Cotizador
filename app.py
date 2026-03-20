streamlit.errors.StreamlitAPIException: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).

Traceback:
File "/mount/src/cotizador/app.py", line 152, in <module>
    st.download_button("📄 Descargar PDF", pdf.output(dest="S"), f"Cot_{nombre_cliente}.pdf", use_container_width=True)
    ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.14/site-packages/streamlit/runtime/metrics_util.py", line 532, in wrapped_func
    result = non_optional_func(*args, **kwargs)
File "/home/adminuser/venv/lib/python3.14/site-packages/streamlit/elements/widgets/button.py", line 771, in download_button
    return self._download_button(
           ~~~~~~~~~~~~~~~~~~~~~^
        label=label,
        ^^^^^^^^^^^^
    ...<14 lines>...
        shortcut=shortcut,
        ^^^^^^^^^^^^^^^^^^
    )
    ^
File "/home/adminuser/venv/lib/python3.14/site-packages/streamlit/elements/widgets/button.py", line 1228, in _download_button
    marshall_file(
    ~~~~~~~~~~~~~^
        self.dg._get_delta_path_str(), data, download_button_proto, mime, file_name
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
File "/home/adminuser/venv/lib/python3.14/site-packages/streamlit/elements/widgets/button.py", line 1560, in marshall_file
    data_as_bytes, inferred_mime_type = convert_data_to_bytes_and_infer_mime(
                                        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        data,
        ^^^^^
    ...<2 lines>...
        ),
        ^^
    )
    ^
File "/home/adminuser/venv/lib/python3.14/site-packages/streamlit/runtime/download_data_util.py", line 51, in convert_data_to_bytes_and_infer_mime
    raise unsupported_error
