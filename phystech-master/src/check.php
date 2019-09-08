<?php

$inputFile  = __DIR__ . '/../example/input.json';
$outputFile = __DIR__ . '/../example/output.json';

if ($argc != 3) {
    echo 'Usage: ' . basename(__FILE__) . ' <source_file> <solution_file>' . PHP_EOL;
    exit;
}

$inputFile  = $argv[1];
$outputFile = $argv[2];

if (!is_file($inputFile) || !is_readable($inputFile)) {
    echo 'Cant find file ' . $inputFile . PHP_EOL;
    exit;
}
if (!is_file($outputFile) || !is_readable($outputFile)) {
    echo 'Cant find file ' . $outputFile . PHP_EOL;
    exit;
}

[$couriers, $orders, $points] = loadData($inputFile);
$events = json_decode(file_get_contents($outputFile), true);

foreach ($events as $step => $event) {
    if (
        !isset($event['courier_id']) ||
        !isset($event['action']) ||
        !isset($event['order_id']) ||
        !isset($event['point_id'])
    ) {
        throw new Exception('Wrong event found');
    }

    $courierId = $event['courier_id'];
    $action    = $event['action'];
    $orderId   = $event['order_id'];
    $pointId   = $event['point_id'];

    if (
        !isset($couriers[$courierId])
        || !isset($points[$pointId])
        || !isset($orders[$orderId])
    ) {
        throw new Exception('Wrong ID found in event');
    }

    $courier = &$couriers[$courierId];
    $point   = &$points[$pointId];
    $order   = &$orders[$orderId];

    // Последнее местоположение курьера
    $courierLocation = $courier['location'];
    // Местоположение точки назначения, куда направляется курьер
    $destinationLocation = $point['location'];
    // Время перемещения до точки назначения
    $durationMinutes = getTravelDurationMinutes($courierLocation, $destinationLocation);
    // Самое раннее время, в которое курьер может оказаться на точке назначения
    $visitTime = $courier['time'] + $durationMinutes;

    if ($visitTime < $point['timewindow'][0]) {
        // Если курьер прибывает раньше левой границы временного интервала на точке, то он ждет начала интервала
        $visitTime = $point['timewindow'][0];
    } elseif ($visitTime > $point['timewindow'][1]) {
        // Если курьер прибывает позже правой границы временного интервала на точке, то это опоздание
        throw new Exception('Courier will be late');
    }

    if ($action == 'pickup') {
        // Если OrderId сейчас не в точке PointId, то это ошибка
        if (!isset($point['order_time'][$orderId])) {
            throw new Exception('Cant pickup');
        }
        // Если курьер едет за заказом на склад, то, возможно, ему нужно будет подождать появления этого заказа на складе
        if (isDepotPoint($pointId) && $visitTime < $point['order_time'][$orderId]) {
            $visitTime = $point['order_time'][$orderId];
        }
        // Курьер забрал заказ, удаляем информацию о том, с какого времени заказ находится в этой точке
        unset($point['order_time'][$orderId]);
    } elseif ($action == 'dropoff') {
        // Если PointId, не id склада или id точки dropoff заказа OrderId, то ошибка (курьер привез заказ не туда)
        if (!isDepotPoint($pointId) && ($pointId != $order['dropoff_point_id'])) {
            throw new Exception('Cant dropoff');
        }
        // Добавляем информацию о времени появления заказа на точке
        $point['order_time'][$orderId] = $visitTime;
    } else {
        throw new Exception('Unknown action');
    }

    // Обновляем время и местоположение курьера
    $courier['time']     = $visitTime;
    $courier['location'] = $destinationLocation;

    echo "{$step}. Courier #{$courierId} {$action} order #{$orderId} at point #{$pointId} at time {$visitTime}", PHP_EOL;
}
unset($point, $order, $courier);

echo 'Routes ok', PHP_EOL;

// Проверяем, что курьеры выполнили все заказы, которые взяли
// И посчитаем общую стоимость выполненных заказов
$hasUnfinishedOrders = false;
$ordersPayment       = 0;
foreach ($orders as $orderId => $order) {
    if (isset($points[$order['dropoff_point_id']]['order_time'][$orderId])) {
        $ordersPayment += $order['payment'];
        echo "Order #{$orderId} completed", PHP_EOL;
    } elseif (isset($points[$order['pickup_point_id']]['order_time'][$orderId])) {
        echo "Order #{$orderId} unassigned", PHP_EOL;
    } else {
        echo "Order #{$orderId} unfinished", PHP_EOL;
        $hasUnfinishedOrders = true;
    }
}

if ($hasUnfinishedOrders) {
    throw new Exception('Not all started orders are completed');
}

echo 'Orders ok', PHP_EOL;

// Считаем общую продолжительность работы курьера в минутах
$workDurationMinutes = array_sum(array_column($couriers, 'time')) - 360 * count($couriers);
$workPayment         = $workDurationMinutes * 2;
$profit              = $ordersPayment - $workPayment;

echo 'Total orders payment: ', $ordersPayment, PHP_EOL;
echo 'Total couriers payment: ', $workPayment, PHP_EOL;
echo 'Profit: ', $profit, PHP_EOL;

/**
 * Время перемещения курьера от точки $location1 до точки $location2 вминутах
 * @param array $location1 [x, y]
 * @param array $location2 [x, y]
 */
function getTravelDurationMinutes(array $location1, array $location2): int {
    $distance = abs($location1[0] - $location2[0]) + abs($location1[1] - $location2[1]);
    return 10 + $distance;
}

/**
 * Загрузка входных данных из файла
 * @param string $file
 * @return array
 */
function loadData(string $file): array {
    $inputData = json_decode(file_get_contents($file), true);
    $couriers  = $orders = $points = [];
    foreach ($inputData['depots'] as $depotData) {
        $points[$depotData['point_id']] = [
            'location'   => [$depotData['location_x'], $depotData['location_y']],
            'timewindow' => [0, 1439], // Промежуточные склады работают целый день [00:00-23:59]
        ];
    }
    foreach ($inputData['couriers'] as $courierData) {
        $couriers[$courierData['courier_id']] = [
            'location' => [$courierData['location_x'], $courierData['location_y']],
            'time'     => 360, // Все курьеры начинают работу в 06:00
        ];
    }
    foreach ($inputData['orders'] as $orderData) {
        $points[$orderData['pickup_point_id']]  = [
            'location'   => [$orderData['pickup_location_x'], $orderData['pickup_location_y']],
            'timewindow' => [$orderData['pickup_from'], $orderData['pickup_to']],
        ];
        $points[$orderData['dropoff_point_id']] = [
            'location'   => [$orderData['dropoff_location_x'], $orderData['dropoff_location_y']],
            'timewindow' => [$orderData['dropoff_from'], $orderData['dropoff_to']],
        ];
        $orders[$orderData['order_id']]         = $orderData;

        $points[$orderData['pickup_point_id']]['order_time'][$orderData['order_id']] = $orderData['pickup_from'];
    }
    return [$couriers, $orders, $points];
}

/**
 * Является ли $pointId точкой склада
 */
function isDepotPoint(int $pointId): bool {
    return $pointId >= 30001 && $pointId <= 40000;
}
