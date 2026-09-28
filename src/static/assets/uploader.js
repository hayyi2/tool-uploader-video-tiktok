const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
$('.select_project').on('shown.bs.dropdown', function () {
    $('.project_name').focus().select().click(function (event) {
        // event.stopPropagation();
        console.log(">> event", event);
    });
});
app.controller("UvtUploaderCtrl", function ($stateParams, $state, $scope, $mdDialog, $http, $q, $filter, $sce, util, toast) {
    $scope.list_projects = null;
    $scope.current_project = {};
    $scope.errors_current_project = {};

    $scope.list_accounts = [];
    $scope.selected_account = null; // interact with modal

    $scope.list_videos_resolved = false;
    $scope.list_videos = [];
    $scope.selected_video = null; // interact with modal
    $scope.query = {
        page: 1,
        limit: 10,
        limit_option: [5, 10, 20, 40, 60],
    };
    $scope.show_upload = true;
    $scope.show_chekcbox = false;

    $scope.data_upload_options = {
        count_per_account: 'Jumlah per akun',
        checked_video: 'Video terpilih',
    };
    $scope.visibility_options = {
        everyone: 'Everyone',
        friends: 'Friends',
        only_you: 'Only you',
    };
    $scope.upload_params = {
        data_upload: 'count_per_account',
        count_per_account: 1,
        checked_video_ids: [],
        visibility: 'everyone',
        allow_comment: true,
        allow_reuse: true,
        disclose_content: false,
        your_brand: false,
        branded_content: false,
        aigc: false,
        copyright: false,
        content_check: false,
        delay_start: 20,
        delay_end: 30,
    };
    $scope.min_schedule = (new Date()).toISOString()

    // util
    this.openMenu = function($mdOpenMenu, ev){
        originatorEv = ev;
        $mdOpenMenu(ev);
    };

    $scope.$watch('upload_params.data_upload', function (newValue, oldValue) {
        if (newValue != oldValue && newValue == 'checked_video') {
            $scope.show_chekcbox = true;
        }
    }, true);

    $scope.values = (data) => data ? Object.values(data) : [];
    $scope.close_dialog = function () {
        $mdDialog.cancel();
    };

    $scope.validate_project_name = function () {
        if ($scope.current_project.name) return;
        $scope.errors_current_project.name = 'Nama project tidak boleh kosong';
        setTimeout(() => {
            $('.select_project_trigger').dropdown('toggle');
            setTimeout(() => {
                $('.project_name').focus().select();
            }, 500);
        }, 100);
    };

    // project handle

    $scope.load_projects = function () {
        const project_id = $stateParams.id;
        $http
            .get($scope._action_url('project/gets'))
            .then(function (res) {
                var resdata = res.data;
                $scope.list_projects = resdata.data;
                let current_project = project_id ? $scope.list_projects.find(p => p.id == project_id) : null;
                if (!current_project) {
                    current_project = $scope.list_projects[0];
                }
                $scope.do_select_project(current_project);
                $scope.validate_project_name();
            }, function () {
                // Error 500/404
                util.alert_dialog('danger', 'Error install', 'Error tidak diketahui!');
            });
    };
    $scope.load_projects();

    var _update_current_project_defer = null;

    $scope.save_current_project = function () {
        if (_update_current_project_defer !== null) {
            _update_current_project_defer.resolve();
        }
        _update_current_project_defer = $q.defer();
        $http({
            method: 'post',
            url: $scope._action_url('project/update'),
            timeout: _update_current_project_defer.promise,
            data: $scope.current_project,
        }).then(function (res) {
            var resdata = res.data;
            $scope.list_projects = $scope.list_projects.map(project => {
                if (project.id === resdata.data.id) {
                    return resdata.data;
                }
                return project;
            });
        });
    };

    $scope.$watch('current_project', function (newValue, oldValue) {
        if (oldValue.id != newValue.id) {
            return;
        }
        if (oldValue.name != newValue.name) {
            $scope.errors_current_project.name = !newValue.name ? 'Nama project tidak boleh kosong' : '';
        }
        for (const key in oldValue) {
            if (oldValue[key] != newValue[key]) {
                $scope.save_current_project();
                break;
            }
        }
    }, true);

    $scope.create_project = function (e) {
        e.preventDefault();
        e.stopPropagation();
        $http
            .post($scope._action_url('project/create'))
            .then(function (res) {
                var resdata = res.data;
                $scope.list_projects = [resdata.data, ...$scope.list_projects];
                $scope.do_select_project(resdata.data);
            }, function () {
                // Error 500/404
                util.alert_dialog('danger', 'Error install', 'Error tidak diketahui!');
            })
            .finally(function () {
                $('.project_name').focus().select();
            });
    };

    $scope.select_project = function (e, project) {
        e.preventDefault();
        $scope.do_select_project(project);
    };

    $scope.do_select_project = function (project) {
        $scope.current_project = project;
        $scope.list_videos_resolved = false;
        $state.go('.', { id: project.id }, {
            location: 'replace',
            inherit: true,
            relative: $state.$current,
            notify: false,
            reload: false
        });
        // reorder list
        $http.post($scope._action_url('project/update'), { id: $scope.current_project.id });
        $scope.load_videos();
    };

    $scope.delete_project = function (e, project) {
        e.preventDefault();
        var confirm = $mdDialog.confirm()
            .title('Delete Project')
            .htmlContent('Apakah kamu yakin mau menghapus project?<br /> Project akan dihapus secara permanen dan tidak bisa dikembalikan.')
            .ok('Delete')
            .cancel('Cancel');
        $mdDialog.show(confirm).then(function () {
            util.loading_dialog();
            $http
                .post($scope._action_url('project/delete'), { id: $scope.current_project.id })
                .then(function (res) {
                    $scope.load_projects();
                    util.alert_dialog('success', 'Success', "Project berhasil di hapus.");
                }, function () {
                    // Error 500/404
                    util.alert_dialog('danger', 'Error install', 'Error tidak diketahui!');
                })
                .finally(function () {
                    util.close_loading_dialog();
                });
        });
    };

    $scope.add_action_ws_receiver({
        add_videos: function (video) {
            $scope.list_videos = [...$scope.list_videos, ...video];
            $scope.$apply();
        },
        edit_videos: function (video) {
            video_index = [];
            for (let i = 0; i < $scope.list_videos.length; i++) {
                video_index[$scope.list_videos[i].id] = i;
            }
            // video = video.map($scope.sort_data_video);
            video.forEach((item) => {
                let update_data = {
                    ...$scope.list_videos[video_index[item.id]],
                    ...item,
                }
                update_data.schedule = new Date(update_data.schedule)
                $scope.list_videos[video_index[item.id]] = update_data;
            });
            $scope.$apply();
        },
        delete_videos: function (ids) {
            ids.forEach((id) => {
                $scope.list_videos.forEach(function (item, index) {
                    if (item.id == id) {
                        $scope.list_videos.splice(index, 1);
                    }
                });
            });
            $scope.$apply();
        },
    });

    // account handle

    $scope.load_accounts = function () {
        $http
            .get($scope._action_url('account/gets_dict_with_products'))
            .then(function (res) {
                var resdata = res.data;
                $scope.list_accounts = resdata.data;
            }, function () {
                // Error 500/404
                util.alert_dialog('danger', 'Error install', 'Error tidak diketahui!');
            });
    };
    $scope.load_accounts();

    // video handle

    $scope.load_videos = function () {
        let pid = $scope.current_project.id;
        $http
            .get($scope._action_url(`video/${pid}/gets`))
            .then(function (res) {
                $scope.list_videos = res.data.data;
                $scope.list_videos_resolved = true;
                $scope.list_videos = $scope.list_videos.map((item) => {
                    item.schedule = new Date(item.schedule);
                    return item;
                })

                // $scope.open_select_account($scope.list_videos[0]);
                // $scope.open_select_showcase($scope.list_videos[0]);
            }, function () {
                // Error 500/404
                util.alert_dialog('danger', 'Error install', 'Error tidak diketahui!');
            });
    };

    $scope.add_folder = function () {
        $http.get($scope._action_url('browse_folder'))
            .then(function (res) {
                if (res.data.success) {
                    $scope.add_folder_path(res.data.folder_path);
                }
            });
    };

    $scope.add_folder_path = function (folder_path) {
        let pid = $scope.current_project.id;
        $http
            .post($scope._action_url(`video/${pid}/add_folder`), { folder_path })
            .then(function (res) {
                if (res.data.success) {
                    if (res.data.data.video_count) {
                        toast.showMessage(`Berhasil menambahkan ${res.data.data.video_count} video.`);
                    } else {
                        toast.showMessage(`Tidak ada video ditambahkan.`);
                    }
                } else {
                    toast.showMessage(res.data.message);
                }
            }, function () {
                // Error 500/404
                util.alert_dialog('danger', 'Error install', 'Error tidak diketahui!');
            });
    };

    var _update_video_defer = {};

    $scope.save_video = function (video) {
        let pid = $scope.current_project.id;
        if (_update_video_defer[video.id]) {
            _update_video_defer[video.id].resolve();
        }
        _update_video_defer[video.id] = $q.defer();
        let payload = { ...video };
        payload.showcase_ids = undefined;
        $http({
            method: 'post',
            url: $scope._action_url(`video/${pid}/update`),
            timeout: _update_video_defer[video.id].promise,
            data: payload,
        });
    };

    $scope.selected_count = function () {
        return $scope.list_videos.map(item => item.checked).filter(item => item).length;
    };
    $scope.can_bulk_change_showcase = function () {
        const account_ids = $scope.list_videos.filter(item => item.checked).map(item => item.account_id)
        if (new Set(account_ids).size !== 1) {
            return false
        }
        return $scope.list_accounts[account_ids[0]].meta.affiliate;
    };
    $scope.bulk_check_all = function () {
        check = $scope.selected_count() == 0;
        for (let index = 0; index < $scope.list_videos.length; index++) {
            $scope.list_videos[index].checked = check;
        }
    };
    $scope.bulk_check = function (check = true) {
        let current_products = $scope.list_videos;
        if ($scope.search && $scope.search.name) {
            current_products = $filter('filter')($scope.list_videos, $scope.search);
        } else {
            current_products = $filter('orderBy')(current_products, $scope.results_order);
            current_products = $filter('limitTo')(current_products, $scope.query.limit, $scope.query.limit * ($scope.query.page - 1));
        }
        current_products.forEach(item => item.checked = check);
    };
    $scope.delete_selected = function () {
        let pid = $scope.current_project.id;
        let ids = [];

        $scope.list_videos.forEach((item) => {
            if (item.checked) {
                ids.push(item.id);
            }
        });
        var confirm = $mdDialog.confirm()
            .title('Delete Videos')
            .htmlContent('Apakah kamu yakin mau menghapus ' + ids.length + ' video?')
            .ok('Delete')
            .cancel('Cancel');

        $mdDialog
            .show(confirm)
            .then(function () {
                $http
                    .post($scope._action_url(`video/${pid}/delete`), { ids })
                    .then(function (res) {
                        if (res.data.success) {
                            toast.showMessage("Video berhasil di hapus.");
                        } else {
                            util.alert_dialog('danger', 'Error Found', res.data.message);
                        }
                    });
            });
    };

    $scope.open_select_account = (video) => {
        $scope.selected_video = video;
        $mdDialog.show({
            clickOutsideToClose: true,
            templateUrl: $scope._static_url('template/dialog/account_select.html'),
            preserveScope: true,
            scope: $scope,
        });
    };

    $scope.select_account = (account) => {
        if ($scope.selected_video.id) {
            $scope.save_video({
                id: $scope.selected_video.id,
                account_id: account.id,
            });
        } else {
            let pid = $scope.current_project.id;
            const video_ids = $scope.list_videos
                .filter(i => i.checked)
                .map(i => i.id);
            $http.post($scope._action_url(`video/${pid}/bulk_update`), {
                ids: video_ids,
                data: {
                    account_id: account.id,
                }
            });
        }
        $scope.close_dialog();
        $scope.selected_video = null;
    };

    $scope.open_select_showcase = (video) => {
        $scope.selected_video = video;
        $scope.selected_account = $scope.list_accounts[$scope.selected_video.account_id];
        for (const key in $scope.selected_account.showcases) {
            $scope.selected_account.showcases[key].checked = $scope.selected_video.showcase_ids.includes(parseInt(key));
        }
        $mdDialog.show({
            clickOutsideToClose: true,
            templateUrl: $scope._static_url('template/dialog/showcase_select.html'),
            preserveScope: true,
            scope: $scope,
        });
    };
    $scope.save_showcase = () => {
        let pid = $scope.current_project.id;
        const showcase_ids = Object.values($scope.selected_account.showcases).filter(i => i.checked).map(i => i.id);
        if ($scope.selected_video.id) {
            $http.post($scope._action_url(`video/${pid}/update`), {
                id: $scope.selected_video.id,
                showcase_ids: showcase_ids,
            });
        } else {
            const video_ids = $scope.list_videos
                .filter(i => i.checked)
                .map(i => i.id);
            $http.post($scope._action_url(`video/${pid}/bulk_update`), {
                ids: video_ids,
                data: {
                    showcase_ids: showcase_ids,
                }
            });
        }
        $scope.close_dialog();
        $scope.selected_video = null;
        $scope.selected_account = null;
    };

    $scope.open_bulk_select_account = () => {
        $scope.selected_video = {};
        $mdDialog.show({
            clickOutsideToClose: true,
            templateUrl: $scope._static_url('template/dialog/account_select.html'),
            preserveScope: true,
            scope: $scope,
        });
    };
    $scope.open_bulk_select_showcase = () => {
        $scope.selected_video = {};
        const videos = $scope.list_videos.filter(i => i.checked);
        $scope.selected_account = $scope.list_accounts[videos[0].account_id];
        $mdDialog.show({
            clickOutsideToClose: true,
            templateUrl: $scope._static_url('template/dialog/showcase_select.html'),
            preserveScope: true,
            scope: $scope,
        });
    };

    $scope.open_bulk_schedule = () => {
        $scope.input_schedule = null;
        $mdDialog.show({
            clickOutsideToClose: true,
            templateUrl: $scope._static_url('template/dialog/bulk_schedule_input.html'),
            preserveScope: true,
            scope: $scope,
        });
    };
    $scope.save_bulk_schedule = () => {
        let pid = $scope.current_project.id;
        const video_ids = $scope.list_videos
            .filter(i => i.checked)
            .map(i => i.id);
        $http.post($scope._action_url(`video/${pid}/bulk_update`), {
            ids: video_ids,
            data: {
                schedule: $scope.input_schedule ?? '',
            }
        });
        $scope.close_dialog();
    };

    // video preview

    $scope.video_cover_url = (video) => {
        let key = video.project_id + '.' + video.id;
        return $scope._action_url(`preview_video_thumb?path=${video.video_path}&key=${key}`);
    };
    $scope.video_preview_url = (video) => {
        return $sce.trustAsResourceUrl($scope._action_url(`preview_video?path=${video.video_path}`));
    };
    $scope.video_over = function (item) {
        item.show_video = true;
        (async () => {
            for (let i = 0; i < 5; i++) {
                videoElement = document.querySelector('#video' + item.id);
                if (videoElement) {
                    try {
                        await videoElement.play();
                        break;
                    } catch (error) {
                    }
                }
                await sleep(200);
            }
        })();
    };
    $scope.video_leave = function (item) {
        item.show_video = false;
        (async () => {
            for (let i = 0; i < 5; i++) {
                videoElement = document.querySelector('#video' + item.id);
                if (videoElement) {
                    try {
                        videoElement.pause();
                        videoElement.currentTime = 0;
                        break;
                    } catch (error) {
                    }
                }
                await sleep(200);
            }
        })();
    };

    // process

    $scope.execute_upload_video = function () {
        util.loading_dialog();
        if ($scope.upload_params.data_upload == 'checked_video') {
            $scope.upload_params.checked_video_ids = $scope.list_videos.filter(v => v.checked).map(v => v.id)
        }

        $http
            .post($scope._action_url('run'), {
                project_id: $scope.current_project.id,
                ...$scope.upload_params,
            })
            .then(function (res) {
                var resdata = res.data;
                if (resdata.success) {
                    $scope.errors_param = {};
                    util.alert_dialog('success', 'Command Executed', 'Silahkan lihat proses lebih detail pada Proses Monitor.');
                } else {
                    util.alert_dialog('danger', 'Error Found', resdata.message);
                }
            }, function () {
                util.alert_dialog('danger', 'Error Found', 'Error tidak diketahui!');
            }).finally(function () {
                util.close_loading_dialog();
            });
    };

});