
app.factory('toast', ['$mdToast',
    function ($mdToast) {
        return {
            showMessage: function (message) {
                return $mdToast.show(
                    $mdToast.simple()
                        .textContent(message)
                        .position("top right")
                        .hideDelay(3000)
                );
            },
        };
    }
]).directive('imgFallback', function() {
    return {
        link: function(scope, element, attrs) {
            element.on('error', function() {
                scope.$apply(function() {
                    scope.$eval(attrs.imgFallback + ' = null');
                });
            });
        }
    };
}).controller("UvtAccountsCtrl", function ($scope, $http, $mdDialog, toast, collection) {
    $scope.list_account = [];
    $scope.list_account_resolved = false;
    $scope.is_loading = false;

    $scope.search = '';
    $scope.setting = {};
    $scope.error_message = '';

    $scope.show_checkbox = false;
    $scope.toggle_show_checkbox = function () {
        $scope.show_checkbox = !$scope.show_checkbox;
    };
    $scope.get_checked = function () {
        return $scope.list_account.filter(i => i.checked);
    };
    $scope.get_checked_count = function () {
        return $scope.list_account.filter(i => i.checked).length;
    };
    $scope.check = function (item) {
        if (!$scope.show_checkbox) return;
        item.checked = !item.checked;
    };
    $scope.check_all = function (value = true) {
        for (const item of $scope.list_account) {
            item.checked = value;
        }
    };

    $scope.close_dialog = function () {
        $mdDialog.cancel();
    };

    $scope.openMenu = function ($mdOpenMenu, ev) {
        $mdOpenMenu(ev);
    };

    /* 
    ws handler
    */

    $scope.add_action_ws_receiver({
        add_accounts: function (account) {
            $scope.list_account = [...$scope.list_account, ...account];
            $scope.$apply();
        },
        edit_accounts: function (account) {
            account_index = [];
            for (let i = 0; i < $scope.list_account.length; i++) {
                account_index[$scope.list_account[i].id] = i;
            }
            // account = account.map($scope.sort_data_account);
            account.forEach((item) => {
                $scope.list_account[account_index[item.id]] = {
                    ...$scope.list_account[account_index[item.id]],
                    ...item,
                };
            });
            $scope.$apply();
        },
        delete_accounts: function (ids) {
            ids.forEach((id) => {
                $scope.list_account.forEach(function (item, index) {
                    if (item.id == id) {
                        $scope.list_account.splice(index, 1);
                    }
                });
            });
            $scope.$apply();
        },
    });

    /*
    manage account
    */

    $scope.load_data = function () {
        $http
            .get($scope._action_url('account'))
            .then(function (res) {
                var resdata = res.data;
                if (resdata.success) {
                    $scope.list_account = resdata.data;
                } else {
                    util.alert_dialog('danger', 'Error Found', resdata.message);
                }
            }, function () {
                util.alert_dialog('danger', 'Error Found', 'Error tidak diketahui!');
            })
            .finally(() => {
                $scope.list_account_resolved = true;
            });
    };
    $scope.load_data();


    $scope.open_input_account_dialog = function (account) {
        $scope.input_mode = account ? 'update' : 'create';
        $scope.error_message = '';
        $scope.input_account = account ? angular.copy(account) : {};

        $mdDialog.show({
            clickOutsideToClose: true,
            templateUrl: $scope._static_url('template/dialog/account_input.html'),
            preserveScope: true,
            scope: $scope,
        });
    };

    $scope.do_input_account = function () {
        $scope.is_loading = true;
        $scope.error_message = '';

        let account = $scope.input_account;
        account.password = account._raw_password;
        $http
            .post($scope._action_url('account/' + $scope.input_mode), account)
            .then(function (res) {
                if (res.data.success) {
                    if ($scope.input_mode == 'update') {
                        toast.showMessage('Updated account saved.');
                    } else {
                        toast.showMessage('Account created.');
                    }
                    $scope.is_loading = false;
                    $mdDialog.cancel();
                } else {
                    $scope.error_message = res.data.message;
                }
            })
            .finally(function () {
                $scope.is_loading = false;
            });
    };

    $scope.delete_account = function (account) {
        var confirm = $mdDialog
            .confirm()
            .title('Delete Account')
            .textContent('Yakin untuk menghapus account?')
            .ok('Delete')
            .cancel('Cancel');

        $mdDialog.show(confirm).then(function () {
            $scope.do_delete_account([account.id])
        });
    };
    $scope.delete_selected_account = function () {
        let selected_account = $scope.get_checked()
        var confirm = $mdDialog
            .confirm()
            .title('Delete Account')
            .textContent(`Yakin untuk menghapus ${selected_account.length} account?`)
            .ok('Delete')
            .cancel('Cancel');

        $mdDialog.show(confirm).then(function () {
            $scope.do_delete_account(selected_account.map(i => i.id))
        });
    };
    $scope.do_delete_account = function (ids) {
        $scope.is_loading = true;
        $http
            .post($scope._action_url('account/delete'), { ids })
            .then(function (response) {
                res = response.data;
                if (res.success) {
                    toast.showMessage('Account deleted.');
                }
            })
            .finally(function () {
                $scope.is_loading = false;
            });
    };


    /*
    adt action
    */

    $scope.autologin_account = function (account) {
        $scope.do_autologin_account([account]);
    };
    $scope.autologin_selected_account = function () {
        $scope.do_autologin_account($scope.get_checked());
    };
    $scope.do_autologin_account = function (accounts) {
        $http
            .post($scope._action_url('account/autologin'), {
                ids: accounts.map(i => i.id),
            })
            .then(function (response) {
                res = response.data;
                if (res.success) {
                    toast.showMessage('Auto login dijalankan, lihat process monitor.');
                } else {
                    toast.showMessage('Auto login failed: ' + res.message);
                }
            }, function () {
                toast.showMessage('Auto login failed: Unknow error');
            })
            .finally(function () {
                $scope.is_loading = false;
            });
    };
    $scope.refresh_account = function (account) {
        $scope.do_refresh_account([account]);
    };
    $scope.refresh_selected_account = function () {
        $scope.do_refresh_account($scope.get_checked());
    };
    $scope.do_refresh_account = function (accounts) {
        $http
            .post($scope._action_url('account/refresh'), {
                ids: accounts.map(i => i.id),
            })
            .then(function (response) {
                // res = response.data;
                // if (res.success) {
                //     toast.showMessage('Auto login dijalankan, lihat process monitor.');
                // } else {
                //     toast.showMessage('Auto login failed: ' + res.message);
                // }
            }, function () {
                toast.showMessage('Auto login failed: Unknow error');
            })
            .finally(function () {
                $scope.is_loading = false;
            });
    };
});