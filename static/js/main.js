<<<<<<< HEAD
(function () {
    'use strict';

    document.querySelectorAll('.flash-dismiss').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var flash = btn.closest('.flash');
            if (flash) {
                flash.style.opacity = '0';
                flash.style.transform = 'translateY(-6px)';
                flash.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
                setTimeout(function () {
                    flash.remove();
                }, 200);
            }
        });
    });

    var dropZone = document.getElementById('drop-zone');
    var fileInput = document.getElementById('file-input');
    var uploadForm = document.getElementById('upload-form');

    if (dropZone && fileInput && uploadForm) {
        ['dragenter', 'dragover'].forEach(function (ev) {
            dropZone.addEventListener(ev, function (e) {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add('drop-zone--active');
            });
        });

        ['dragleave', 'drop'].forEach(function (ev) {
            dropZone.addEventListener(ev, function (e) {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove('drop-zone--active');
            });
        });

        dropZone.addEventListener('drop', function (e) {
            var incoming = e.dataTransfer && e.dataTransfer.files;
            if (incoming && incoming.length) {
                var bucket = new DataTransfer();
                bucket.items.add(incoming[0]);
                fileInput.files = bucket.files;
            }
        });

        dropZone.addEventListener('click', function () {
            fileInput.click();
        });

        dropZone.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                fileInput.click();
            }
        });
    }

    var filterInput = document.querySelector('[data-files-filter]');
    var filesTable = document.getElementById('files-table');
    if (filterInput && filesTable) {
        var rows = filesTable.querySelectorAll('tbody tr[data-filter-name]');
        filterInput.addEventListener('input', function () {
            var q = filterInput.value.trim().toLowerCase();
            rows.forEach(function (row) {
                var name = row.getAttribute('data-filter-name') || '';
                if (!q || name.indexOf(q) !== -1) {
                    row.classList.remove('file-row-hidden');
                } else {
                    row.classList.add('file-row-hidden');
                }
            });
        });
    }
})();
=======
// Shared JavaScript — add as needed
>>>>>>> origin/main
